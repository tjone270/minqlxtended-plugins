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
import requests
import itertools
import threading
import random
import time

RATING_KEY = "minqlx:players:{0}:ratings:{1}"  # 0 == steam_id, 1 == short gametype.
MAX_ATTEMPTS = 3
CACHE_EXPIRE = 60 * 10  # 10 minutes TTL.
DEFAULT_RATING = 1500
UNTRACKED_RATING = 9999
SUPPORTED_GAMETYPES = ("ad", "ca", "ctf", "dom", "ft", "tdm")
# Externally supported game types. Used by !getrating for game types the API works with.
EXT_SUPPORTED_GAMETYPES = ("ad", "ca", "ctf", "dom", "ft", "tdm", "duel", "ffa")


class balance(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("round_countdown", self.handle_round_countdown)
        self.add_hook("round_start", self.handle_round_start)
        self.add_hook("vote_ended", self.handle_vote_ended)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("new_game", self.handle_new_game)
        self.add_command(("setrating", "setelo"), self.cmd_setrating, 3, usage="<id> <rating>")
        self.add_command(("getrating", "getelo", "elo"), self.cmd_getrating, usage="<id> [gametype]")
        self.add_command(("remrating", "remelo"), self.cmd_remrating, 3, usage="<id>")
        self.add_command("balance", self.cmd_balance, 1, client_cmd_perm=1)
        self.add_command(("teams", "teens"), self.cmd_teams)
        self.add_command("do", self.cmd_do, 1)
        self.add_command(("dl", "do_later"), self.cmd_do_later, 1, client_cmd_perm=1)
        self.add_command(("agree", "a"), self.cmd_agree, client_cmd_perm=0)
        self.add_command(("ratings", "elos", "selo"), self.cmd_ratings)

        self.ratings_lock = threading.RLock()
        # Keys: steam_id - Items: {"ffa": {"elo": 123, "games": 321, "local": False}, ...}
        self.ratings = {}
        # Keys: steam_id - Items: {"deactivated": true/false, "ratings": {...}, "allowRating": true/false, "privacy": "public/private/anonymous/untracked"}
        self.player_info = {}
        # Keys: request_id - Items: (players, callback, channel)
        self.requests = {}
        self.request_counter = itertools.count()
        self.suggested_pair = None
        self.suggested_agree = [False, False]
        self.in_countdown = False

        self.set_cvar_once("qlx_balanceUseLocal", "1")
        self.set_cvar_once("qlx_balanceLocalExpires", "0")
        self.set_cvar_once("qlx_balanceUrl", "qlstats.net")
        self.set_cvar_once("qlx_balanceAuto", "1")
        self.set_cvar_once("qlx_balanceMinimumSuggestionDiff", "25")
        self.set_cvar_once("qlx_balanceMinimumSuggestionActionDiff", "50")
        self.set_cvar_once("qlx_balanceCancelSuggestionAfterRound", "1")
        self.set_cvar_once("qlx_balanceApi", "elo")

        self._cache_cvars()

    def _cache_cvars(self):
        """we do this to prevent lots of unnecessary engine calls"""
        self._api_url = f"http://{self.get_cvar('qlx_balanceUrl')}/{self.get_cvar('qlx_balanceApi')}/"
        self._qlx_balanceUseLocal = self.get_cvar("qlx_balanceUseLocal", bool)
        self._qlx_balanceLocalExpires = self.get_cvar("qlx_balanceLocalExpires", int)
        self._qlx_balanceCancelSuggestionAfterRound = self.get_cvar("qlx_balanceCancelSuggestionAfterRound", bool)
        self._qlx_balanceAuto = self.get_cvar("qlx_balanceAuto", bool)
        self._qlx_balanceMinimumSuggestionDiff = self.get_cvar("qlx_balanceMinimumSuggestionDiff", float)
        self._qlx_balanceMinimumSuggestionActionDiff = self.get_cvar("qlx_balanceMinimumSuggestionActionDiff", float)

    def handle_round_countdown(self, *args, **kwargs):
        self.in_countdown = True
        if all(self.suggested_agree):
            # If we don't delay the switch a bit, the round countdown sound and
            # text disappears for some weird reason.
            @minqlxtended.next_frame
            def f():
                self.execute_suggestion()

            f()
        elif (any(self.suggested_agree)) and (self._qlx_balanceCancelSuggestionAfterRound):
            for player, agreed in zip(self.suggested_pair, self.suggested_agree):
                if not agreed:
                    continue

                try:
                    player.update()
                    agreed_player = player
                except minqlxtended.NonexistentPlayerError:
                    self.suggested_pair = None
                    self.suggested_agree = [False, False]
                    return

            if agreed_player:
                self.msg(f"As only ^6{agreed_player.clean_name}^7 agreed, the suggestion has been cancelled.")

            self.suggested_pair = None
            self.suggested_agree = [False, False]
        elif (self.suggested_pair != None) and (self._qlx_balanceCancelSuggestionAfterRound):
            self.msg("As no-one agreed, the suggestion has been cancelled.")
            self.suggested_pair = None
            self.suggested_agree = [False, False]

    def handle_round_start(self, *args, **kwargs):
        self.in_countdown = False

    def handle_vote_ended(self, votes, vote, args, passed):
        if passed == True and vote == "shuffle" and self._qlx_balanceAuto:
            gt = self.game.type_short
            if gt not in SUPPORTED_GAMETYPES:
                return

            @minqlxtended.delay(3.5)
            def f():
                players = self.teams()
                if len(players["red"] + players["blue"]) % 2 != 0:
                    self.msg("Teams were ^6NOT^7 balanced due to the total number of players being an odd number.")
                    return

                players = dict([(p.steam_id, gt) for p in players["red"] + players["blue"]])
                self.add_request(players, self.callback_balance, minqlxtended.CHAT_CHANNEL)

            f()

    def handle_player_disconnect(self, player, reason):
        self.clean_player_data(player)

    def handle_new_game(self):
        self._cache_cvars()

        # reset ratings cache on start
        if self.game.state == "warmup":
            with self.ratings_lock:
                self.ratings = {}

    @minqlxtended.thread
    def clean_player_data(self, player):
        for p in self.players().copy():
            if p.steam_id == player.steam_id and p.id != player.id:
                # there is a second client with same steam id
                return

        if player.steam_id in self.player_info:
            del self.player_info[player.steam_id]

        with self.ratings_lock:
            if player.steam_id in self.ratings:
                del self.ratings[player.steam_id]

    @minqlxtended.thread
    def fetch_ratings(self, players, request_id):
        if not players:
            return

        # We don't want to modify the actual dict, so we use a copy.
        players = players.copy()

        # Get local ratings if present in DB.
        if self._qlx_balanceUseLocal:
            for steam_id in players.copy():
                gt = players[steam_id]
                key = RATING_KEY.format(steam_id, gt)
                if key in self.db:
                    with self.ratings_lock:
                        if steam_id in self.ratings:
                            self.ratings[steam_id][gt] = {"games": -1, "elo": int(self.db[key]), "local": True, "time": -1}
                        else:
                            self.ratings[steam_id] = {gt: {"games": -1, "elo": int(self.db[key]), "local": True, "time": -1}}
                    del players[steam_id]

            if not players:
                self.handle_ratings_fetched(request_id, requests.codes.ok)
                return

        attempts = 0
        last_status = 0
        untracked_sids = []

        while attempts < MAX_ATTEMPTS:
            attempts += 1
            url = self._api_url + "+".join([str(sid) for sid in players])
            res = requests.get(url, headers={"X-QuakeLive-Map": self.game.map})
            last_status = res.status_code
            if res.status_code != requests.codes.ok:
                continue

            js = res.json()
            if "players" not in js:
                last_status = -1
                continue

            # Fill our ratings dict with the ratings we just got.
            for p in js["players"]:
                sid = int(p["steamid"])
                del p["steamid"]
                t = time.time()

                with self.ratings_lock:
                    if sid not in self.ratings:
                        self.ratings[sid] = {}

                    for gt in p:
                        p[gt]["time"] = t
                        p[gt]["local"] = False
                        self.ratings[sid][gt] = p[gt]
                        if self.ratings[sid][gt]["elo"] == 0 and self.ratings[sid][gt]["games"] == 0:
                            self.ratings[sid][gt]["elo"] = DEFAULT_RATING

                        if sid in players and gt == players[sid]:
                            # The API gave us the game type we wanted, so we remove it.
                            del players[sid]

                    # Fill the rest of the game types the API didn't return but supports.
                    for gt in SUPPORTED_GAMETYPES:
                        if gt not in self.ratings[sid]:
                            self.ratings[sid][gt] = {"games": -1, "elo": DEFAULT_RATING, "local": False, "time": time.time()}

            # If the API didn't return all the players, we set them to the default rating.
            for sid in players:
                with self.ratings_lock:
                    if sid not in self.ratings:
                        self.ratings[sid] = {}
                    self.ratings[sid][players[sid]] = {"games": -1, "elo": DEFAULT_RATING, "local": False, "time": time.time()}

            # Setting ratings for untracked players.
            if "untracked" in js:
                untracked_sids = list(map(lambda sid: int(sid), js["untracked"]))

            for gt in SUPPORTED_GAMETYPES:
                for sid in untracked_sids:
                    with self.ratings_lock:
                        if sid not in self.ratings:
                            self.ratings[sid] = {}
                        self.ratings[sid][gt] = {"games": -1, "elo": UNTRACKED_RATING, "local": False, "time": time.time()}

            # Saving player info
            try:
                for player, data in js["playerinfo"].items():
                    sid = int(player)
                    self.player_info[sid] = js["playerinfo"][player]
                    self.player_info[sid]["time"] = time.time()
            except KeyError:
                pass

            break

        if attempts == MAX_ATTEMPTS:
            self.handle_ratings_fetched(request_id, last_status)
            return

        self.handle_ratings_fetched(request_id, requests.codes.ok)

    @minqlxtended.next_frame
    def handle_ratings_fetched(self, request_id, status_code):
        players, callback, channel, args = self.requests[request_id]
        del self.requests[request_id]
        if status_code != requests.codes.ok:
            # TODO: Put a couple of known errors here for more detailed feedback.
            channel.reply(f"ERROR {status_code}: Failed to fetch ratings.")
        else:
            callback(players, channel, *args)

    def add_request(self, players, callback, channel, *args):
        req = next(self.request_counter)
        self.requests[req] = players.copy(), callback, channel, args

        # Only start a new thread if we need to make an API request.
        if self.remove_cached(players):
            self.fetch_ratings(players, req)
        else:
            # All players were cached, so we tell it to go ahead and call the callbacks.
            self.handle_ratings_fetched(req, requests.codes.ok)

    def remove_cached(self, players):
        with self.ratings_lock:
            for sid in players.copy():
                gt = players[sid]
                if sid in self.ratings and gt in self.ratings[sid]:
                    t = self.ratings[sid][gt]["time"]
                    if t == -1 or time.time() < t + CACHE_EXPIRE:
                        del players[sid]

        return players

    def cmd_getrating(self, player, msg, channel):
        """Fetch the rating of the player ID supplied, or of the calling player if no ID supplied."""
        if len(msg) == 1:
            sid = player.steam_id
        else:
            if not self.db.has_permission(player, 2):  # purgery issue #6
                channel.reply(f"Using the ^4{msg[0]}^7 command to obtain other player's ratings is disabled on this server.")
                return minqlxtended.RET_STOP

            try:
                sid = int(msg[1])
                target_player = None
                if 0 <= sid < 64:
                    target_player = self.player(sid)
                    sid = target_player.steam_id
            except ValueError:
                player.tell("Invalid ID. Use either a client ID or a SteamID64.")
                return minqlxtended.RET_STOP_ALL
            except minqlxtended.NonexistentPlayerError:
                player.tell("Invalid client ID. Use either a client ID or a SteamID64.")
                return minqlxtended.RET_STOP_ALL

        if len(msg) > 2:
            if msg[2].lower() in EXT_SUPPORTED_GAMETYPES:
                gt = msg[2].lower()
            else:
                player.tell(f"Invalid gametype. Supported gametypes: {', '.join(EXT_SUPPORTED_GAMETYPES)}")
                return minqlxtended.RET_STOP_ALL
        else:
            gt = self.game.type_short
            if gt not in EXT_SUPPORTED_GAMETYPES:
                player.tell("This game mode is not supported by the balance plugin.")
                return minqlxtended.RET_STOP_ALL

        self.add_request({sid: gt}, self.callback_getrating, channel, gt)

    def callback_getrating(self, players, channel, gametype):
        sid = next(iter(players))
        player = self.player(sid)
        if player:
            name = player.name
        else:
            name = sid

        channel.reply(f"{name}^7 has a rating of ^6{self.ratings[sid][gametype]['elo']}^7 in {gametype.upper()}.")

    def cmd_setrating(self, player, msg, channel):
        """Manually set the rating of a player. Depending on server configuration, this manually-set rating may expire after a pre-determined timeframe."""
        if len(msg) < 3:
            return minqlxtended.RET_USAGE

        try:
            sid = int(msg[1])
            target_player = None
            if 0 <= sid < 64:
                target_player = self.player(sid)
                sid = target_player.steam_id
        except ValueError:
            player.tell("Invalid ID. Use either a client ID or a SteamID64.")
            return minqlxtended.RET_STOP_ALL
        except minqlxtended.NonexistentPlayerError:
            player.tell("Invalid client ID. Use either a client ID or a SteamID64.")
            return minqlxtended.RET_STOP_ALL

        try:
            rating = int(msg[2])
        except ValueError:
            player.tell("Invalid rating.")
            return minqlxtended.RET_STOP_ALL

        if target_player:
            name = target_player.name
        else:
            name = sid

        gt = self.game.type_short
        self.db[RATING_KEY.format(sid, gt)] = rating
        if self._qlx_balanceLocalExpires:
            self.db.expire(RATING_KEY.format(sid, gt), self._qlx_balanceLocalExpires)

        # If we have the player cached, set the rating.
        with self.ratings_lock:
            if sid in self.ratings and gt in self.ratings[sid]:
                self.ratings[sid][gt]["elo"] = rating
                self.ratings[sid][gt]["local"] = True
                self.ratings[sid][gt]["time"] = -1

        channel.reply(f"{name}'s {gt.upper()} rating has been set to ^6{rating}^7.")

    def cmd_remrating(self, player, msg, channel):
        """Remove a manually-set rating for a player."""
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            sid = int(msg[1])
            target_player = None
            if 0 <= sid < 64:
                target_player = self.player(sid)
                sid = target_player.steam_id
        except ValueError:
            player.tell("Invalid ID. Use either a client ID or a SteamID64.")
            return minqlxtended.RET_STOP_ALL
        except minqlxtended.NonexistentPlayerError:
            player.tell("Invalid client ID. Use either a client ID or a SteamID64.")
            return minqlxtended.RET_STOP_ALL

        if target_player:
            name = target_player.name
        else:
            name = sid

        gt = self.game.type_short

        try:
            del self.db[RATING_KEY.format(sid, gt)]
        except KeyError:
            channel.reply(f"{name}^7 does not have a locally set rating.")
            return minqlxtended.RET_STOP_ALL

        # If we have the player cached, remove the game type.
        with self.ratings_lock:
            if sid in self.ratings and gt in self.ratings[sid]:
                del self.ratings[sid][gt]

        channel.reply(f"{name}^7's locally set {gt.upper()} rating has been deleted.")

    def cmd_balance(self, player, msg, channel):
        """Balance the teams according to player ratings, by distributing players evenly. Requires that the total number of players should be an even number."""
        gt = self.game.type_short
        if gt not in SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.RET_STOP_ALL

        teams = self.teams()
        if len(teams["red"] + teams["blue"]) % 2 != 0:
            player.tell("The total number of players should be an even number.")
            return minqlxtended.RET_STOP_ALL

        players = dict([(p.steam_id, gt) for p in teams["red"] + teams["blue"]])
        self.add_request(players, self.callback_balance, minqlxtended.CHAT_CHANNEL)

    def callback_balance(self, players, channel):
        # We check if people joined while we were requesting ratings and get them if someone did.
        teams = self.teams()
        current = teams["red"] + teams["blue"]
        gt = self.game.type_short

        for p in current:
            if p.steam_id not in players:
                d = dict([(p.steam_id, gt) for p in current])
                self.add_request(d, self.callback_balance, channel)
                return

        # Start out by evening out the number of players on each team.
        diff = len(teams["red"]) - len(teams["blue"])
        if abs(diff) > 1:
            if diff > 0:
                for i in range(diff - 1):
                    p = teams["red"].pop()
                    p.put("blue")
                    teams["blue"].append(p)
            elif diff < 0:
                for i in range(abs(diff) - 1):
                    p = teams["blue"].pop()
                    p.put("red")
                    teams["red"].append(p)

        # Start shuffling by looping through our suggestion function until
        # there are no more switches that can be done to improve teams.
        switch = self.suggest_switch(teams, gt)
        if switch:
            while switch:
                p1 = switch[0][0]
                p2 = switch[0][1]
                self.switch(p1, p2)
                teams["blue"].append(p1)
                teams["red"].append(p2)
                teams["blue"].remove(p2)
                teams["red"].remove(p1)
                switch = self.suggest_switch(teams, gt)
            avg_red = self.team_average(teams["red"], gt)
            avg_blue = self.team_average(teams["blue"], gt)
            diff_rounded = abs(round(avg_red) - round(avg_blue))  # Round individual averages.
            if round(avg_red) > round(avg_blue):
                self.msg(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - DIFFERENCE: ^1{diff_rounded}")
            elif round(avg_red) < round(avg_blue):
                self.msg(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - DIFFERENCE: ^4{diff_rounded}")
            else:
                self.msg(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - Holy shit!")
        else:
            channel.reply("Teams are good! Nothing to balance.")
        return True

    def cmd_teams(self, player, msg, channel):
        """Displays the current rating difference between teams."""
        gt = self.game.type_short
        if gt not in SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.RET_STOP_ALL

        teams = self.teams()
        if len(teams["red"]) != len(teams["blue"]):
            player.tell("Both teams should have the same number of players.")
            return minqlxtended.RET_STOP_ALL

        teams = dict([(p.steam_id, gt) for p in teams["red"] + teams["blue"]])
        self.add_request(teams, self.callback_teams, channel)

    def callback_teams(self, players, channel):
        # We check if people joined while we were requesting ratings and get them if someone did.
        teams = self.teams()
        current = teams["red"] + teams["blue"]
        gt = self.game.type_short

        for p in current:
            if p.steam_id not in players:
                d = dict([(p.steam_id, gt) for p in current])
                self.add_request(d, self.callback_teams, channel)
                return

        avg_red = self.team_average(teams["red"], gt)
        avg_blue = self.team_average(teams["blue"], gt)
        switch = self.suggest_switch(teams, gt)
        diff_rounded = abs(round(avg_red) - round(avg_blue))  # Round individual averages.
        if round(avg_red) > round(avg_blue):
            channel.reply(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - DIFFERENCE: ^1{diff_rounded}")
        elif round(avg_red) < round(avg_blue):
            channel.reply(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - DIFFERENCE: ^4{diff_rounded}")
        else:
            channel.reply(f"^1{round(avg_red)} ^7vs ^4{round(avg_blue)}^7 - Holy shit!")

        minimum_suggestion_diff = self._qlx_balanceMinimumSuggestionDiff
        minimum_suggestion_action_diff = self._qlx_balanceMinimumSuggestionActionDiff
        if (switch) and (switch[1] >= minimum_suggestion_diff):
            if (switch[1] >= minimum_suggestion_action_diff) and (self.game.state == "in_progress"):
                channel.reply(f"BALANCING: switching ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7 at the beginning of the next round.")
            elif (switch[1] >= minimum_suggestion_action_diff) and (self.game.state != "in_progress"):
                channel.reply(f"BALANCING: now switching ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7.")
            else:
                channel.reply(f"SUGGESTION: switch ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7. Mentioned players can type !a to agree.")

            if (not self.suggested_pair) or (self.suggested_pair[0] != switch[0][0]) or (self.suggested_pair[1] != switch[0][1]):
                self.suggested_pair = (switch[0][0], switch[0][1])
                if (switch[1] >= minimum_suggestion_action_diff) and (self.game.state == "in_progress"):
                    self.suggested_agree = [True, True]
                elif (switch[1] >= minimum_suggestion_action_diff) and (self.game.state != "in_progress"):
                    self.execute_suggestion()
                else:
                    self.suggested_agree = [False, False]
        else:
            channel.reply("Teams look good!")
            self.suggested_pair = None

        return True

    def cmd_do(self, player, msg, channel):
        """Forces a player switch as suggested by the balancer to be done."""
        if self.suggested_pair:
            self.execute_suggestion()

    def cmd_do_later(self, player, msg, channel):
        """Forces a player switch as suggested by the balancer to be done at the beginning of the next round."""
        if self.suggested_pair is not None:
            self.suggested_agree[0] = True
            self.suggested_agree[1] = True
            channel.reply("The switch will occur at the beginning of the next round.")
        else:
            channel.reply("There is no switch suggestion available to do later.")

    def cmd_agree(self, player, msg, channel):
        """After the balancer suggests a switch, players in question can use this command to indicate agreement to the switch."""
        if self.suggested_pair and not all(self.suggested_agree):
            p1, p2 = self.suggested_pair

            if p1 == player:
                self.suggested_agree[0] = True
            elif p2 == player:
                self.suggested_agree[1] = True

            if all(self.suggested_agree):
                # If the game's in progress and we're not in the round countdown, wait for next round.
                if self.game.state == "in_progress" and not self.in_countdown:
                    self.msg("The switch will be executed at the start of next round.")
                    return

                # Otherwise, switch right away.
                self.execute_suggestion()

    def cmd_ratings(self, player, msg, channel):
        """List the ratings for each player, grouped by teams."""
        gt = self.game.type_short
        if gt not in EXT_SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.RET_STOP_ALL

        if not self.db.has_permission(player, 2):
            player.tell(f"The ^4{msg[0]}^7 command has been disabled on this server, except by moderators.")
            return minqlxtended.RET_STOP_ALL

        players = dict([(p.steam_id, gt) for p in self.players()])
        self.add_request(players, self.callback_ratings, channel)

    def callback_ratings(self, players, channel):
        # We check if people joined while we were requesting ratings and get them if someone did.
        teams = self.teams()
        current = self.players()
        gt = self.game.type_short

        for p in current:
            if p.steam_id not in players:
                d = dict([(p.steam_id, gt) for p in current])
                self.add_request(d, self.callback_ratings, channel)
                return

        if teams["free"]:
            free_sorted = sorted(teams["free"], key=lambda x: self.ratings[x.steam_id][gt]["elo"], reverse=True)
            free = ", ".join([f"{p.clean_name}: ^6{self.ratings[p.steam_id][gt]['elo']}^7" for p in free_sorted])
            channel.reply(free)
        if teams["red"]:
            red_sorted = sorted(teams["red"], key=lambda x: self.ratings[x.steam_id][gt]["elo"], reverse=True)
            red = ", ".join([f"{p.clean_name}: ^1{self.ratings[p.steam_id][gt]['elo']}^7" for p in red_sorted])
            channel.reply(red)
        if teams["blue"]:
            blue_sorted = sorted(teams["blue"], key=lambda x: self.ratings[x.steam_id][gt]["elo"], reverse=True)
            blue = ", ".join([f"{p.clean_name}: ^4{self.ratings[p.steam_id][gt]['elo']}^7" for p in blue_sorted])
            channel.reply(blue)
        if teams["spectator"]:
            spec_sorted = sorted(teams["spectator"], key=lambda x: self.ratings[x.steam_id][gt]["elo"], reverse=True)
            spec = ", ".join([f"{p.clean_name}: {self.ratings[p.steam_id][gt]['elo']}" for p in spec_sorted])
            channel.reply(spec)

    def suggest_switch(self, teams, gametype):
        """Suggest a switch based on average team ratings."""
        avg_red = self.team_average(teams["red"], gametype)
        avg_blue = self.team_average(teams["blue"], gametype)
        cur_diff = abs(avg_red - avg_blue)
        min_diff = 999999
        best_pair = None

        for red_p in teams["red"]:
            for blue_p in teams["blue"]:
                r = teams["red"].copy()
                b = teams["blue"].copy()
                b.append(red_p)
                r.remove(red_p)
                r.append(blue_p)
                b.remove(blue_p)
                avg_red = self.team_average(r, gametype)
                avg_blue = self.team_average(b, gametype)
                diff = abs(avg_red - avg_blue)
                if diff < min_diff:
                    min_diff = diff
                    best_pair = (red_p, blue_p)

        if min_diff < cur_diff:
            return (best_pair, cur_diff - min_diff)
        else:
            return None

    def team_average(self, team, gametype):
        """Calculates the average rating of a team."""
        avg = 0
        if team:
            for p in team:
                avg += self.ratings[p.steam_id][gametype]["elo"]
            avg /= len(team)

        return avg

    def execute_suggestion(self):
        p1, p2 = self.suggested_pair
        try:
            p1.update()
            p2.update()
        except minqlxtended.NonexistentPlayerError:
            return

        if p1.team != "spectator" and p2.team != "spectator":
            p1stats, p1score = p1.stats, p1.score
            p2stats, p2score = p2.stats, p2.score
            self.switch(p1, p2)

            @minqlxtended.delay(1)
            def f(p1, p2, p1stats, p2stats, p1score, p2score):
                p1.stats, p1.score = p1stats, p1score
                p2.stats, p2.score = p2stats, p2score

            f(p1, p2, p1stats, p2stats, p1score, p2score)

        self.suggested_pair = None
        self.suggested_agree = [False, False]
