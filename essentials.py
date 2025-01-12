# minqlx - A Quake Live server administrator bot.
# Copyright (C) 2015 Mino <mino@minomino.org>

# This file is part of minqlxtended.

# minqlx is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlx is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlxtended. If not, see <http://www.gnu.org/licenses/>.


import minqlxtended
import datetime
import itertools
import time
import re
import os

from random import randint
from collections import deque

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"

class essentials(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("vote_called", self.handle_vote_called)
        self.add_hook("command", self.handle_command, priority=minqlxtended.PRI_LOW)
        self.add_hook("client_command", self.handle_client_command)
        self.add_command(("id", "players"), self.cmd_list_players, client_cmd_perm=0)
        self.add_command(("disconnects", "dcs"), self.cmd_disconnects, 1)
        self.add_command(("commands", "cmds"), self.cmd_commands, 2)
        self.add_command("shuffle", self.cmd_shuffle, 1, client_cmd_perm=1)
        self.add_command(("pause", "timeout"), self.cmd_pause, 1)
        self.add_command(("unpause", "timein"), self.cmd_unpause, 1)
        self.add_command("slap", self.cmd_slap, 2, usage="<id> [damage]")
        self.add_command("slay", self.cmd_slay, 2, usage="<id>")
        self.add_command("sounds", self.cmd_enable_sounds, usage="<0/1>", client_cmd_perm=0)
        self.add_command("sound", self.cmd_sound, 1, usage="<path>")
        self.add_command("music", self.cmd_music, 1, usage="<path>")
        self.add_command("stopsound", self.cmd_stopsound, 1)
        self.add_command("stopmusic", self.cmd_stopmusic, 1)
        self.add_command("kick", self.cmd_kick, 2, usage="<id>")
        self.add_command(("kickban", "tempban"), self.cmd_kickban, 2, usage="<id>")
        self.add_command("yes", self.cmd_yes, 2)
        self.add_command("no", self.cmd_no, 2)
        self.add_command("random", self.cmd_random, 1, usage="<limit>")
        self.add_command("cointoss", self.cmd_cointoss, 1)
        self.add_command("switch", self.cmd_switch, 1, usage="<id> <id>")
        self.add_command("red", self.cmd_red, 1, usage="<id>")
        self.add_command("blue", self.cmd_blue, 1, usage="<id>")
        self.add_command(("spectate", "spec", "spectator"), self.cmd_spectate, 1, usage="<id>")
        self.add_command("free", self.cmd_free, 1, usage="<id>")
        self.add_command("addmod", self.cmd_addmod, 5, usage="<id>")
        self.add_command("addadmin", self.cmd_addadmin, 5, usage="<id>")
        self.add_command("demote", self.cmd_demote, 5, usage="<id>")
        self.add_command("mute", self.cmd_mute, 1, usage="<id>")
        self.add_command("unmute", self.cmd_unmute, 1, usage="<id>")
        self.add_command("lock", self.cmd_lock, 1, usage="[team]")
        self.add_command("unlock", self.cmd_unlock, 1, usage="[team]")
        self.add_command("allready", self.cmd_allready, 2)
        self.add_command("abort", self.cmd_abort, 2)
        self.add_command(("map", "changemap"), self.cmd_map, 2, usage="<mapname> [factory]")
        self.add_command(("help", "about", "version"), self.cmd_help, client_cmd_perm=0)
        self.add_command(("seen", "lastseen"), self.cmd_last_seen, usage="<steam_id>")
        self.add_command("firstseen", self.cmd_first_seen, usage="<id>/<steam_id>")
        self.add_command("time", self.cmd_time, usage="[timezone_offset]")
        self.add_command(("teamsize", "ts"), self.cmd_teamsize, 2, usage="<size>")
        self.add_command("rcon", self.cmd_rcon, 5)
        self.add_command(("mappool", "maps", "maplist"), self.cmd_mappool, client_cmd_perm=0)

        # CVARs.
        self.set_cvar_once("qlx_votepass", "1")
        self.set_cvar_limit_once("qlx_votepassThreshold", "0.33", "0", "1")
        self.set_cvar_once("qlx_teamsizeMinimum", "1")
        self.set_cvar_once("qlx_teamsizeMaximum", "8")
        self.set_cvar_once("qlx_enforceMappool", "0")

        # Vote counter. We use this to avoid automatically passing votes we shouldn't.
        self.vote_count = itertools.count()
        self.last_vote = 0

        # A short history of recently executed commands.
        self.recent_cmds = deque(maxlen=11)
        # A short history of recently disconnected players.
        self.recent_dcs = deque(maxlen=10)
        
        # Map voting stuff. fs_homepath takes precedence.
        self.mappool = None
        mphome = os.path.join(self.get_cvar("fs_homepath", str),
            "baseq3", self.get_cvar("sv_mappoolfile"))
        if os.path.isfile(mphome):
            self.mappool = self.parse_mappool(mphome)
        else:
            mpbase = os.path.join(self.get_cvar("fs_basepath", str),
                "baseq3", self.get_cvar("sv_mappoolfile"))
            if os.path.isfile(mpbase):
                self.mappool = self.parse_mappool(mpbase)

    def handle_player_connect(self, player):
        self.update_player(player)

    def handle_player_disconnect(self, player, reason):
        self.recent_dcs.appendleft((player, time.time()))
        self.update_seen_player(player)

    def handle_vote_called(self, caller, vote, args):
        # Enforce teamsizes.
        if vote.lower() == "teamsize":
            try:
                args = int(args)
            except ValueError:
                return
            
            if args > self.get_cvar("qlx_teamsizeMaximum", int):
                caller.tell("The team size is larger than what the server allows.")
                return minqlxtended.RET_STOP_ALL
            elif args < self.get_cvar("qlx_teamsizeMinimum", int):
                caller.tell("The team size is smaller than what the server allows.")
                return minqlxtended.RET_STOP_ALL
        
        # Enforce map pool.
        if vote.lower() == "map" and self.mappool and self.get_cvar("qlx_enforceMappool", bool):
            split_args = args.split()
            if len(split_args) == 0:
                caller.tell("Available maps and factories:")
                self.tell_mappool(caller, indent=2)
                return minqlxtended.RET_STOP_ALL
            
            map_name = split_args[0].lower()
            factory = split_args[1] if len(split_args) > 1 else self.game.factory
            if map_name in self.mappool:
                if factory and factory not in self.mappool[map_name]:
                    caller.tell("This factory is not allowed on that map. Use {}mappool to see available options."
                        .format(self.get_cvar("qlx_commandPrefix")))
                    return minqlxtended.RET_STOP_ALL
            else:
                caller.tell("This map is not allowed. Use {}mappool to see available options."
                    .format(self.get_cvar("qlx_commandPrefix")))
                return minqlxtended.RET_STOP_ALL
        
        # Automatic vote passing.
        if self.get_cvar("qlx_votepass", bool):
            self.last_vote = next(self.vote_count)
            self.force(self.get_cvar("qlx_votepassThreshold", float), self.last_vote)

    def handle_command(self, caller, command, args):
        self.recent_cmds.appendleft((caller, command, args))

    def handle_client_command(self, player, command):
        if command.lower() == "players":
            self.send_player_list(player)
            return minqlxtended.RET_STOP_ALL
        elif command.lower() == "players.":
            self.send_player_list(player, True)
            return minqlxtended.RET_STOP_ALL

    def cmd_list_players(self, player, msg, channel):
        """ Sends the player list to the caller. """
        self.send_player_list(player)
        return minqlxtended.RET_STOP_ALL

    def cmd_disconnects(self, player, msg, channel):
        """ Sends the list of most recent player disconnects to the caller. """
        if len(self.recent_dcs) == 0:
            player.tell("No players have disconnected yet.")
        else:
            player.tell("The most recent ^6{}^7 player disconnects:".format(len(self.recent_dcs)))
            for x in self.recent_dcs:
                p, t = x
                player.tell("  {} ({}): ^6{}^7 seconds ago".format(p.name, p.steam_id, round(time.time() - t)))

        return minqlxtended.RET_STOP_ALL

    def cmd_commands(self, player, msg, channel):
        """ Sends the list of the most recently used commands to the caller. """
        if len(self.recent_cmds) == 1:
            player.tell("No commands have been recorded yet.")
        else:
            player.tell("The most recent ^6{}^7 commands executed:".format(len(self.recent_cmds) - 1))
            for cmd in list(self.recent_cmds)[1:]:
                player.tell("  {} executed: {}".format(cmd[0].name, cmd[2]))

        return minqlxtended.RET_STOP_ALL

    def cmd_shuffle(self, player, msg, channel):
        """ Forces a shuffle instantly. """
        self.shuffle()

    def cmd_pause(self, player, msg, channel):
        """ Pauses the game. """
        self.pause()

    def cmd_unpause(self, player, msg, channel):
        """ Unpauses the game. """
        self.unpause()

    def cmd_slap(self, player, msg, channel):
        """ Slaps a player with optional damage specified. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            player.tell("Invalid ID.")
            return minqlxtended.RET_STOP_ALL

        if len(msg) > 2:
            try:
                dmg = int(msg[2])
            except ValueError:
                player.tell("Invalid damage value.")
                return minqlxtended.RET_STOP_ALL
        else:
            dmg = 0
        
        self.slap(target_player, dmg)
        return minqlxtended.RET_STOP_ALL

    def cmd_slay(self, player, msg, channel):
        """ Kills the specified player instantly. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            player.tell("Invalid ID.")
            return minqlxtended.RET_STOP_ALL

        self.slay(target_player)
        return minqlxtended.RET_STOP_ALL

    def cmd_enable_sounds(self, player, msg, channel):
        """ Prevents custom sounds from playing for the calling player. Use again to re-enable these sounds. """
        flag = self.db.get_flag(player, "essentials:sounds_enabled", default=True)
        self.db.set_flag(player, "essentials:sounds_enabled", not flag)
        
        if flag:
            player.tell("Sounds have been disabled. Use ^6{}sounds^7 to enable them again."
                .format(self.get_cvar("qlx_commandPrefix")))
        else:
            player.tell("Sounds have been enabled. Use ^6{}sounds^7 to disable them again."
                .format(self.get_cvar("qlx_commandPrefix")))

        return minqlxtended.RET_STOP_ALL

    def cmd_sound(self, player, msg, channel):
        """ Plays a sound for the those who have it enabled. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        if not self.db.get_flag(player, "essentials:sounds_enabled", default=True):
            player.tell("Sounds are disabled. Use ^6{}sounds^7 to enable them again."
                .format(self.get_cvar("qlx_commandPrefix")))
            return minqlxtended.RET_STOP_ALL

        # Play locally to validate.
        if not self.play_sound(msg[1], player):
            player.tell("Invalid sound.")
            return minqlxtended.RET_STOP_ALL

        # Play to all other players who haven't disabled sound
        players = self.players()
        players.remove(player)
        for p in players:
            if self.db.get_flag(p, "essentials:sounds_enabled", default=True):
                self.play_sound(msg[1], p)

        return minqlxtended.RET_STOP_ALL

    def cmd_music(self, player, msg, channel):
        """ Plays music, but only for those with music volume on and the sounds flag on. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        if not self.db.get_flag(player, "essentials:sounds_enabled", default=True):
            player.tell("Sounds are disabled. Use ^6{}sounds^7 to enable them again."
                .format(self.get_cvar("qlx_commandPrefix")))
            return minqlxtended.RET_STOP_ALL

        # Play locally to validate.
        if not self.play_music(msg[1], player):
            player.tell("Invalid sound.")
            return minqlxtended.RET_STOP_ALL

        # Play to all other players who haven't disabled sounds.
        players = self.players()
        players.remove(player)
        for p in players:
            if self.db.get_flag(p, "essentials:sounds_enabled", default=True):
                self.play_music(msg[1], p)

        return minqlxtended.RET_STOP_ALL

    def cmd_stopsound(self, player, msg, channel):
        """ Stops all sounds playing. Useful if someone plays one of those really long ones. """
        if not self.db.get_flag(player, "essentials:sounds_enabled", default=True):
            player.tell("Sounds are disabled. Use ^6{}sounds^7 to enable them again."
                .format(self.get_cvar("qlx_commandPrefix")))
            return minqlxtended.RET_STOP_ALL

        self.stop_sound()

    def cmd_stopmusic(self, player, msg, channel):
        """ Stops any music playing. """
        if not self.db.get_flag(player, "essentials:sounds_enabled", default=True):
            player.tell("Sounds are disabled. Use ^6{}sounds^7 to enable them again."
                .format(self.get_cvar("qlx_commandPrefix")))
            return minqlxtended.RET_STOP_ALL

        self.stop_music()

    def cmd_kick(self, player, msg, channel):
        """ Kicks a player. A reason can also be provided, which appears for the player in the 'server disconnected' dialog. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return
        
        if len(msg) > 2:
            target_player.kick(" ".join(msg[2:]))
        else:
            target_player.kick()

    def cmd_kickban(self, player, msg, channel):
        """ Kicks a player and prevent the player from joining for the remainder of the current map. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.tempban()

    def cmd_yes(self, player, msg, channel):
        """ Passes the currently active vote. """
        if self.is_vote_active():
            self.force_vote(True)
        else:
            channel.reply("There is no active vote!")

    def cmd_no(self, player, msg, channel):
        """ Vetoes the currently active vote. """
        if self.is_vote_active():
            self.force_vote(False)
        else:
            channel.reply("There is no active vote!")

    def cmd_random(self, player, msg, channel):
        """ Presents a random number in chat. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        try:
            n = randint(1,int(msg[1]))
        except ValueError:
            player.tell("Invalid upper limit. Use a positive integer.")
            return minqlxtended.RET_STOP_ALL
        
        channel.reply("^3Random number is: ^5{}".format(n))
        
    def cmd_cointoss(self, player, msg, channel):
        """ Tosses a coin, and returns HEADS or TAILS in chat. """
        n = randint(0,1)
        channel.reply("^3The coin is: ^5{}".format("HEADS" if n else "TAILS"))
        
    def cmd_switch(self, player, msg, channel):
        """ Switches the teams of the two players specified. """
        if len(msg) < 3:
            return minqlxtended.RET_USAGE

        try:
            i1 = int(msg[1])
            player1 = self.player(i1)
            if not (0 <= i1 < 64) or not player1:
                raise ValueError
        except ValueError:
            channel.reply("The first ID is invalid.")
            return

        try:
            i2 = int(msg[2])
            player2 = self.player(i2)
            if not (0 <= i2 < 64) or not player2:
                raise ValueError
        except ValueError:
            channel.reply("The second ID is invalid.")
            return

        self.switch(player1, player2)
            
    def cmd_red(self, player, msg, channel):
        """ Moves the specified player to the red team. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.put("red")

    def cmd_blue(self, player, msg, channel):
        """ Moves the specified player to the blue team. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.put("blue")


    def cmd_spectate(self, player, msg, channel):
        """ Moves the specified player to the spectator team. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.put("spectator")

    def cmd_free(self, player, msg, channel):
        """ Moves the specified player to the free team (the 'team' used in non-team gametypes like Free For All.) """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.put("free")

    def cmd_addmod(self, player, msg, channel):
        """ Give a player classic moderator status. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.addmod()

    def cmd_addadmin(self, player, msg, channel):
        """ Give a player classic administrator status. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.addadmin()

    def cmd_demote(self, player, msg, channel):
        """ Remove classic administrator/moderator status from someone. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.demote()

    def cmd_mute(self, player, msg, channel):
        """ Mutes the specified player. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        if target_player == player:
            channel.reply("I refuse.")
        else:
            target_player.mute()

    def cmd_unmute(self, player, msg, channel):
        """ /Unmutes the specified player. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            channel.reply("Invalid ID.")
            return

        target_player.unmute()

    def cmd_lock(self, player, msg, channel):
        """ Locks the specified team. """
        if len(msg) > 1:
            if msg[1][0].lower() == "s":
                self.lock("spectator")
            elif msg[1][0].lower() == "r":
                self.lock("red")
            elif msg[1][0].lower() == "b":
                self.lock("blue")
            else:
                player.tell("Invalid team.")
                return minqlxtended.RET_STOP_ALL
        else:
            self.lock()

    def cmd_unlock(self, player, msg, channel):
        """ Unlocks the specified team. """
        if len(msg) > 1:
            if msg[1][0].lower() == "s":
                self.unlock("spectator")
            elif msg[1][0].lower() == "r":
                self.unlock("red")
            elif msg[1][0].lower() == "b":
                self.unlock("blue")
            else:
                player.tell("Invalid team.")
                return minqlxtended.RET_STOP_ALL
        else:
            self.unlock()
    
    def cmd_allready(self, player, msg, channel):
        """ Forces all players to ready up. """
        if self.game.state == "warmup":
            self.allready()
        else:
            channel.reply("But the game's already in progress, you silly goose!")
        
    def cmd_abort(self, player, msg, channel):
        """ Forces a game currently in progress to go back to warm-up. """
        if self.game.state != "warmup":
            self.abort()
        else:
            channel.reply("But the game isn't even on, you doofus!")
    
    def cmd_map(self, player, msg, channel):
        """ Changes the map to the one specified (using the optionally specifiable factory.) """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        # TODO: Give feedback on !map.
        self.change_map(msg[1], msg[2] if len(msg) > 2 else None)
        
    def cmd_help(self, player, msg, channel):
        """ Provide minqlxtended version information. """
        channel.reply("minqlxtended: ^6{}^7 - Plugins: ^6{}".format(minqlxtended.__version__, minqlxtended.__plugins_version__))
        channel.reply("See ^4github.com/tjone270/minqlxtended^7 for more information.")

    def cmd_first_seen(self, player, msg, channel):
        """ Responds with the first time a player was seen on the server. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            steam_id = int(msg[1])
            target_player = None
            if 0 <= steam_id < 64:
                target_player = self.player(steam_id)
                steam_id = target_player.steam_id
        except ValueError:
            channel.reply("Invalid ID. Use either a client ID or a SteamID64.")
            return
        except minqlxtended.NonexistentPlayerError:
            channel.reply("Invalid client ID. Use either a client ID or a SteamID64.")
            return
        
        if target_player:
            name = target_player.name + "^7"
        else:
            name = "that player" if steam_id != minqlxtended.owner() else "my ^4master^7"

        key = "minqlx:players:{}:first_seen".format(steam_id)
        if key in self.db:
            then = datetime.datetime.strptime(self.db[key], DATETIME_FORMAT)
            td = datetime.datetime.now() - then
            r = re.match(r'((?P<d>.*) days*, )?(?P<h>..?):(?P<m>..?):.+', str(td))
            if r.group("d"):
                channel.reply("^7I first saw {} ^6{}^7 day{}, ^6{}^7 hour{} and ^6{}^7 minute{} ago."
                    .format(name,
                            int(r.group("d")), self.plural(r.group("d")),
                            int(r.group("h")), self.plural(r.group("h")),
                            int(r.group("m")), self.plural(r.group("m"))))
            else:
                channel.reply("^7I first saw {} ^6{}^7 hour{} and ^6{}^7 minute{} ago."
                    .format(name,
                            int(r.group("h")), self.plural(r.group("h")),
                            int(r.group("m")), self.plural(r.group("m"))))
        else:
            if "minqlx:players:{}".format(steam_id) in self.db:
                channel.reply("^7That player is ^6too old^7 to have that date recorded.")
            else:
                channel.reply("^7I have never seen ^6{}^7 before.".format(name))

    def cmd_last_seen(self, player, msg, channel):
        """ Responds with the last time a player was seen on the server. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            steam_id = int(msg[1])
            if steam_id < 64:
                channel.reply("Invalid SteamID64.")
                return
        except ValueError:
            channel.reply("Unintelligible SteamID64.")
            return
        
        p = self.player(steam_id)
        if p:
            channel.reply("That would be {}^7, who is currently on this very server!".format(p))
            return
        
        key = "minqlx:players:{}:last_seen".format(steam_id)
        name = "that player" if steam_id != minqlxtended.owner() else "my ^6master^7"
        if key in self.db:
            then = datetime.datetime.strptime(self.db[key], DATETIME_FORMAT)
            td = datetime.datetime.now() - then
            r = re.match(r'((?P<d>.*) days*, )?(?P<h>..?):(?P<m>..?):.+', str(td))
            if r.group("d"):
                channel.reply("^7I last saw {} ^6{}^7 day{}, ^6{}^7 hour{} and ^6{}^7 minute{} ago."
                    .format(name,
                            int(r.group("d")), self.plural(r.group("d")),
                            int(r.group("h")), self.plural(r.group("h")),
                            int(r.group("m")), self.plural(r.group("m"))))
            else:
                channel.reply("^7I last saw {} ^6{}^7 hour{} and ^6{}^7 minute{} ago."
                    .format(name,
                            int(r.group("h")), self.plural(r.group("h")),
                            int(r.group("m")), self.plural(r.group("m"))))
        else:
            channel.reply("^7I have never seen {} before.".format(name))

    def cmd_time(self, player, msg, channel):
        """ Responds with the current time. """
        tz_offset = time.timezone if (time.localtime().tm_isdst == 0) else time.altzone
        tz_offset = tz_offset // 60 // 60 * -1
        if len(msg) > 1:
            try:
                tz_offset = int(msg[1])
            except ValueError:
                channel.reply("Unintelligible time zone offset.")
                return
        tz = datetime.timezone(offset=datetime.timedelta(hours=tz_offset))
        now = datetime.datetime.now(tz)
        if tz_offset > 0:
            channel.reply("The current time is: ^6{} UTC+{}"
                .format(now.strftime(TIME_FORMAT), tz_offset))
        elif tz_offset < 0:
            channel.reply("The current time is: ^6{} UTC{}"
                .format(now.strftime(TIME_FORMAT), tz_offset))
        else:
            channel.reply("The current time is: ^6{} UTC"
                .format(now.strftime(TIME_FORMAT)))

    def cmd_teamsize(self, player, msg, channel):
        """ Alters the teamsize to that specified. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        try:
            n = int(msg[1])
        except ValueError:
            channel.reply("^7Unintelligible size.")
            return
        
        self.game.teamsize = n
        self.msg("The teamsize has been set to ^6{}^7 by {}^7.".format(n, player))
        return minqlxtended.RET_STOP_ALL

    def cmd_rcon(self, player, msg, channel):
        """ Sends a console command to the server. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        with minqlxtended.redirect_print(channel):
            minqlxtended.console_command(" ".join(msg[1:]))

    def cmd_mappool(self, player, msg, channel):
        """ If a map pool is currently enforced, responds with the currently allowed maps. """
        if not self.mappool:
            player.tell("The map pool is currently unavailable.")
            return

        self.tell_mappool(player)

        if not self.get_cvar("qlx_enforceMappool", bool):
            player.tell("No map pool is currently enforced. You are free to vote any map.")

        return minqlxtended.RET_STOP_ALL


    # ====================================================================
    #                               HELPERS
    # ====================================================================

    def update_player(self, player):
        """Updates the list of recent names and IPs used by the player,
        and adds entries to the player list and IP entries.

        """
        base_key = "minqlx:players:" + str(player.steam_id)
        db = self.db.pipeline()
        
        # Add to IP set and make IP entry.
        if player.ip:
            db.sadd("minqlx:ips", player.ip)
            db.sadd("minqlx:ips:" + player.ip, player.steam_id)
            db.sadd(base_key + ":ips", player.ip)
        
        # Make or update player entry.
        if base_key not in self.db:
            db.lpush(base_key, player.name)
            db.sadd("minqlx:players", player.steam_id)
            db.set(base_key + ":first_seen", datetime.datetime.now().strftime(DATETIME_FORMAT))
        else:
            names = [self.clean_text(n) for n in self.db.lrange(base_key, 0, -1)]
            if player.clean_name not in names:
                db.lpush(base_key, player.name)
                db.ltrim(base_key, 0, 19)

        if player.name:
            # Record the player's latest name.
            db.set("{}:current_name".format(base_key), player.name)
        
        db.execute()

    def update_seen_player(self, player):
        key = "minqlx:players:" + str(player.steam_id) + ":last_seen"
        self.db[key] = datetime.datetime.now().strftime(DATETIME_FORMAT)
        
    @minqlxtended.delay(29)
    def force(self, require, vote_id):
        if self.last_vote != vote_id:
            # This is not the vote we should be resolving.
            return

        votes = self.current_vote_count()
        if self.is_vote_active() and votes and votes[0] > votes[1]:
            if require:
                teams = self.teams()
                players = teams["red"] + teams["blue"] + teams["free"]
                if sum(votes)/len(players) < require:
                    return
            minqlxtended.force_vote(True)
    
    def parse_mappool(self, path):
        """Read and parse the map pool file into a dictionary.
    
        Structure as follows:
        {'campgrounds': ['ca', 'ffa'], 'overkill': ['ca']}
        
        """
        mappool = {}
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except:
            minqlxtended.log_exception()
            return None
        
        for line in lines:
            li = line.lstrip()
            # Ignore commented lines.
            if not li.startswith("#") and "|" in li:
                key, value = line.split('|', 1)
                # Maps are case-insensitive, but not factories.
                key = key.lower()

                if key in mappool:
                    mappool[key].append(value.strip())
                else:
                    mappool[key] = [value.strip()]
        
        return mappool

    def tell_mappool(self, player, indent=0):
        out = ""
        for m in sorted(self.mappool.items(), key=lambda x: x[0]):
            out += ("Map: {0}^6{1:25}^7 Factories: ^6{2}^7\n"
                .format(" " * indent, m[0], ", ".join(val for val in m[1])))
        player.tell(out.rstrip("\n"))

    def plural(self, sample):
        return "s" if int(sample) != 1 else ""
    
    def send_player_list(self, target_player, ease_sight = False):
        players = self.players()
        target_player.tell("^6 Steam ID            ID    Ping  Perm  Player")
        for player in players:
            type_chars = [f"^{str(self.db.get_permission(player))*2}^7", " "]
            if player.steam_id == minqlxtended.owner(): 
                type_chars[1] = "*" # owner
            elif player.is_bot:
                type_chars[0] = ""
                type_chars[1] = "ʙ" # bot

            ping_colour = "7"
            if player.ping > 160:
                ping_colour = "1"
            elif player.ping > 80:
                ping_colour = "3"
            elif player.ping > 0:
                ping_colour = "2"

            line = f" {player.steam_id} | {player.id:>2} | ^{ping_colour}{player.ping:>3}ms^7 | {''.join(type_chars)} | {player.name}"
            
            if ease_sight: # fenix849
                line = line.replace(" ", ".")

            target_player.tell(line)
