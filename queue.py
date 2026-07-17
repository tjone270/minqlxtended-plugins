# queue.py - a plugin for minqlxtended to allow players to queue politely for fair and even gameplay.
# Copyright (C) 2016 mattiZed (github)
# Copyright (C) 2016 Melodeiro (github)

# You can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# You should have received a copy of the GNU General Public License
# along with minqlxtended. If not, see <http://www.gnu.org/licenses/>.

# Updated 31/07/2024 to make compatible with minqlxtended.
# Reworked to be single-threaded/race-free: minqlxtended runs everything on the main
# game thread, and this plugin has no blocking I/O, so the previous @minqlxtended.thread
# usage only introduced data races on the shared _queue/_afk/_tags structures. All shared
# state is now mutated exclusively on the main/frame thread; the debounced re-push uses
# @minqlxtended.delay instead of time.sleep in a worker thread.

import minqlxtended

TEAM_BASED_GAMETYPES = ("ca", "ctf", "dom", "ft", "tdm", "ad", "1f", "har")
NONTEAM_BASED_GAMETYPES = ("ffa", "race", "rr", "duel")
CS_PLAYERS = 529
NO_CLANTAG_FLAG_NAME = "no_clantag"

_tag_key = "minqlx:players:{}:clantag"

class queue(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("new_game", self.handle_new_game)
        self.add_hook("game_end", self.handle_game_end)
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("team_switch_attempt", self.handle_team_switch_attempt)
        self.add_hook("set_configstring", self.handle_configstring, priority=minqlxtended.PRI_HIGH)
        self.add_hook("client_command", self.handle_client_command)
        self.add_hook("vote_ended", self.handle_vote_ended)
        self.add_hook("console_print", self.handle_console_print)
        self.add_command(("q", "queue", "que"), self.cmd_lq)
        self.add_command("afk", self.cmd_afk, usage="<optional player ID>")
        self.add_command("here", self.cmd_playing)
        self.add_command(("teamsize", "ts"), self.cmd_teamsize, priority=minqlxtended.PRI_HIGH)

        self._queue = []
        self._afk = []
        self._tags = {}

        # These flags must exist before initialize() or any scheduled push runs.
        self.is_red_locked = False
        self.is_blue_locked = False
        self.is_endscreen = False  # set True between game_end and the next new_game
        self._push_scheduled = False  # main-thread debounce for pushFromQueue

        self.set_cvar_once("qlx_queueSetAfkPermission", "2")
        self.set_cvar_once("qlx_queueAFKTag", "^3AFK")

        self._cache_variables()
        self.initialize()


    def _cache_variables(self):
        """ we do this to prevent lots of unnecessary engine calls """
        self._qlx_queueSetAfkPermission = self.get_cvar("qlx_queueSetAfkPermission", int)
        self._qlx_queueAFKTag = self.get_cvar("qlx_queueAFKTag")
        self._sv_maxclients = self.get_cvar("sv_maxclients", int)

    def initialize(self):
        for p in self.players():
            self.updTag(p)
        self.unlock()

    def center_print(self, *args, **kwargs):
        pass

    ## Basic List Handling (Queue and AFK)
    def addToQueue(self, player, pos=-1):
        """Safely adds players to the queue"""
        if player not in self._queue:
            if pos == -1:
                self._queue.append(player)
            else:
                self._queue.insert(pos, player)
                for p in self._queue:
                    self.updTag(p)
            for p in self.teams()['spectator']:
                p.center_print(f"{player.name}^7 joined the queue")
        if player in self._queue:
            player.center_print("You are in the queue to play")
        self.updTag(player)
        self.pushFromQueue()

    def remFromQueue(self, player, update=True):
        """Safely removes player from the queue"""
        if player in self._queue:
            self._queue.remove(player)
        for p in self._queue:
            self.updTag(p)
        if update:
            self.updTag(player)

    def pushFromQueue(self, delay=0):
        """Debounced request to fill/even teams from the queue.

        Always runs on the main/frame thread. The single boolean guard is race-free because
        it is only ever read/written on that one thread; a push requested while one is pending
        is coalesced, and the flag is cleared at the start of the scheduled run so genuine
        follow-up pushes re-arm a fresh window (preserving the original 0.5s cadence).
        """
        if self._push_scheduled:
            return
        self._push_scheduled = True

        if delay and delay > 0:
            @minqlxtended.delay(delay)
            def run():
                self._push_scheduled = False
                self._do_push()
            run()
        else:
            @minqlxtended.next_frame
            def run():
                self._push_scheduled = False
                self._do_push()
            run()

    def _do_push(self):
        if not self._queue:
            return
        if self.game.state != 'in_progress' and self.game.state != 'warmup':
            return
        if self.is_endscreen:
            return
        self._check_for_place()

    def _check_for_place(self):
        """Check if there is space and players in the queue, and put them in the game."""
        maxplayers = self.get_maxplayers()
        teams = self.teams()
        red_amount = len(teams["red"])
        blue_amount = len(teams["blue"])
        free_amount = len(teams["free"])
        pushed = False

        if self.game.type_short in TEAM_BASED_GAMETYPES:
            diff = red_amount - blue_amount
            if diff > 0 and not self.is_blue_locked:
                pushed = self._push_to_team(diff, "blue")
            elif diff < 0 and not self.is_red_locked:
                pushed = self._push_to_team(-diff, "red")
            elif red_amount + blue_amount < maxplayers:
                if len(self._queue) > 1 and not self.is_blue_locked and not self.is_red_locked:
                    pushed = self._push_to_both()
                elif self.game.state == 'warmup':  # for the case if there is 1 player in queue
                    if not self.is_red_locked and red_amount < int(self.game.teamsize):
                        pushed = self._push_to_team(1, "red")
                    elif not self.is_blue_locked and blue_amount < int(self.game.teamsize):
                        pushed = self._push_to_team(1, "blue")
        elif self.game.type_short in NONTEAM_BASED_GAMETYPES:
            if free_amount < maxplayers:
                pushed = self._push_to_team(maxplayers - free_amount, "free")

        # Only re-arm if we placed someone, so we keep draining the queue across
        # 0.5s cycles without spinning forever when nobody can currently be placed.
        if pushed:
            self.pushFromQueue(0.5)

    def _push_to_team(self, amount, team):
        """Move up to `amount` front-of-queue, ACTIVE spectators onto `team`.

        Disconnected/zombie entries are dropped; still-loading (connected/primed) entries are
        kept in place. The inspected element is popped (never a blind pop(0)), and the list is
        never iterated while being mutated. Returns True if at least one player was placed.
        """
        if self.is_endscreen:
            return False
        placed = 0
        changed = False
        spectators = self.teams()['spectator']
        i = 0
        while placed < amount and i < len(self._queue):
            qplayer = self._queue[i]
            if qplayer in spectators and qplayer.connection_state == 'active':
                self._queue.pop(i)
                qplayer.put(team)
                placed += 1
                changed = True
                spectators = self.teams()['spectator']  # refresh the now-stale snapshot
            elif qplayer.connection_state not in ('connected', 'primed'):
                self._queue.pop(i)  # gone for good; drop and re-inspect this index
                changed = True
            else:
                i += 1  # connected/primed: still loading, keep and move past it
        if changed:
            for p in self._queue:
                self.updTag(p)
        return placed > 0

    def _push_to_both(self):
        """Place the two front-of-queue players onto red and blue at once."""
        if self.is_endscreen or len(self._queue) <= 1:
            return False
        spectators = self.teams()['spectator']
        first = self._queue[0]
        if first in spectators and first.connection_state == 'active':
            second = self._queue[1]
            if second in spectators and second.connection_state == 'active':
                self._queue.pop(0).put("red")
                self._queue.pop(0).put("blue")
                for p in self._queue:
                    self.updTag(p)
                return True
            elif second.connection_state not in ('connected', 'primed'):
                self.remFromQueue(second)
        elif first.connection_state not in ('connected', 'primed'):
            self.remFromQueue(first)
        return False

    def remAFK(self, player, update=True):
        """Safely removes players from afk list"""
        if player in self._afk:
            self._afk.remove(player)
            if update:
                self.updTag(player)

    def posInQueue(self, player):
        """Returns position of the player in queue"""
        try:
            return self._queue.index(player)
        except ValueError:
            return -1

    ## AFK Handling
    def setAFK(self, player):
        """Returns True if player's state could be set to AFK"""
        if player in self.teams()['spectator'] and player not in self._afk:
            self._afk.append(player)
            self.remFromQueue(player)
            return True
        return False

    def remTag(self, player):
        if player.steam_id in self._tags:
            del self._tags[player.steam_id]

    def updTag(self, player):
        """Update the tags dictionary and start the set_configstring event for tag to apply"""
        @minqlxtended.next_frame
        def upd():
            if player in self.players():
                player.clan = player.clan

        if player in self.players():
            addition = ""
            position = self.posInQueue(player)

            if position > -1:
                addition = f'({position + 1})'
            elif player in self._afk:
                addition = f'({self._qlx_queueAFKTag})'
            elif self.game.type_short not in TEAM_BASED_GAMETYPES + NONTEAM_BASED_GAMETYPES:
                addition = ""
            elif player in self.teams()['spectator']:
                addition = '(s)'

            self._tags[player.steam_id] = addition

            upd()

    def get_maxplayers(self):
        maxplayers = int(self.game.teamsize)
        if self.game.type_short in TEAM_BASED_GAMETYPES:
            maxplayers = maxplayers * 2
        if maxplayers == 0:
            maxplayers = self._sv_maxclients
        return maxplayers

    ## Plugin Handles and Commands
    def handle_player_disconnect(self, player, reason):
        self.remAFK(player, False)
        self.remFromQueue(player, False)
        self.remTag(player)
        self.pushFromQueue(0.5)

    def handle_player_loaded(self, player):
        self.updTag(player)

    def handle_team_switch(self, player, old_team, new_team):
        if new_team != "spectator":
            self.remFromQueue(player)
            self.remAFK(player)
        else:
            self.updTag(player)
            self.pushFromQueue(0.5)

    def handle_team_switch_attempt(self, player, old_team, new_team):
        if self.game.type_short not in TEAM_BASED_GAMETYPES + NONTEAM_BASED_GAMETYPES:
            return

        if new_team != "spectator" and old_team == "spectator":
            teams = self.teams()
            maxplayers = self.get_maxplayers()
            if len(teams["red"]) + len(teams["blue"]) == maxplayers or len(teams["free"]) == maxplayers or self.game.state == 'in_progress' or len(self._queue) > 0 or self.is_red_locked or self.is_blue_locked:
                self.remAFK(player)
                self.addToQueue(player)
                return minqlxtended.RET_STOP_ALL

    def handle_client_command(self, player, command):
        if (command.lower().strip() == "team s") and (player.team == "spectator"):
            self.remFromQueue(player)
            if player not in self._queue:
                # self.center_print is overridden to a no-op in this plugin; send it
                # to the player directly so the confirmation reaches them.
                player.center_print("You are set to spectate only")

    def handle_vote_ended(self, votes, vote, args, passed):
        if vote.lower().strip() == "teamsize":
            self.pushFromQueue(4)

    def handle_configstring(self, index, value):
        if not value:
            return

        elif CS_PLAYERS <= index < CS_PLAYERS + 64:
            try:
                player = self.player(index - CS_PLAYERS)
            except minqlxtended.NonexistentPlayerError:
                return

            if player.steam_id in self._tags:
                tag = self._tags[player.steam_id]

                # only run if player is allowed to use clan tags
                if not self.db.get_flag(player, NO_CLANTAG_FLAG_NAME):
                    tag_key = _tag_key.format(player.steam_id)
                    dbtag = self.db.get(tag_key)  # single GET; None when absent (was EXISTS + GET)
                    if dbtag is not None:
                        if len(tag) > 0:
                            tag += ' '
                        tag += dbtag

                cs = minqlxtended.parse_variables(value)
                cs["xcn"] = tag
                cs["cn"] = tag
                new_cs = "".join([f"\\{key}\\{cs[key]}" for key in cs])
                return new_cs

    def handle_new_game(self):
        self.is_endscreen = False
        self.is_red_locked = False
        self.is_blue_locked = False

        if self.game.type_short not in TEAM_BASED_GAMETYPES + NONTEAM_BASED_GAMETYPES:
            self._queue = []
            for p in self.players():
                self.updTag(p)
        else:
            self.pushFromQueue()

    def handle_game_end(self, data):
        self.is_endscreen = True

    def cmd_lq(self, player, msg, channel):
        """ Display the current queue. """
        msg = "^7No one in queue."
        if self._queue:
            msg = "^1Queue^7: "
            count = 1
            for p in self._queue:
                msg += f'{p.name}^7({count}) '
                count += 1
        channel.reply(msg)

        if self._afk:
            msg = "^3Away^7 >> "
            for p in self._afk:
                msg += p.name + " "

            channel.reply(msg)

    def cmd_afk(self, player, msg, channel):
        """ Marks the calling player as AFK (or the player specified.) """
        if len(msg) > 1:
            if not self.db.has_permission(player, self._qlx_queueSetAfkPermission):
                player.tell("^7You do not have permission to set other players AFK.")
                return minqlxtended.RET_STOP_ALL

            matches = self.find_player(msg[1])
            if not matches:
                player.tell(f"^7No players matching ^6{msg[1]}^7 were found.")
                return minqlxtended.RET_STOP_ALL
            if len(matches) > 1:
                player.tell(f"^7More than one player matches ^6{msg[1]}^7. Please be more specific.")
                return minqlxtended.RET_STOP_ALL

            guy = matches[0]
            if self.setAFK(guy):
                player.tell(f"Status for {guy.name}^7 has been set to ^3AFK^7.")
            else:
                player.tell(f"Couldn't set status for {guy.name}^7 to ^3AFK^7.")
            return minqlxtended.RET_STOP_ALL

        if self.setAFK(player):
            player.tell("^7Your status has been set to ^3AFK^7.")
        else:
            player.tell("^7Couldn't set your status to ^3AFK^7.")

    def cmd_playing(self, player, msg, channel):
        """ Marks the calling player as available. """
        self.remAFK(player)
        self.updTag(player)
        player.tell("Your status has been set to ^2AVAILABLE^7.")

    def cmd_teamsize(self, playing, msg, channel):
        self.pushFromQueue(0.5)

    def handle_console_print(self, text):
        if text.find('broadcast: print "The RED team is now locked') != -1:
            self.is_red_locked = True
        elif text.find('broadcast: print "The BLUE team is now locked') != -1:
            self.is_blue_locked = True
        elif text.find('broadcast: print "The RED team is now unlocked') != -1:
            self.is_red_locked = False
            self.pushFromQueue(0.5)
        elif text.find('broadcast: print "The BLUE team is now unlocked') != -1:
            self.is_blue_locked = False
            self.pushFromQueue(0.5)
