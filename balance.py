# minqlxtended - Extends Quake Live's dedicated server with extra functionality and scripting.
# Copyright (C) 2015 Mino <mino@minomino.org>
# Copyright (C) 2016-2026 Thomas Jones <me@thomasjones.id.au>

# This file is part of minqlxtended.

# minqlxtended is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlxtended is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlxtended. If not, see <http://www.gnu.org/licenses/>.

import minqlxtended
import requests
import itertools
import threading
import time

BALANCE_TIMEOUT = (3.05, 10)

_session = requests.Session()

RATING_KEY = "minqlx:players:{0}:ratings:{1}"  # 0 == steam_id, 1 == short gametype.
MAX_ATTEMPTS = 3
CACHE_EXPIRE = 60 * 10  # 10 minutes TTL.
DEFAULT_RATING = 1500
UNTRACKED_RATING = 9999
SUPPORTED_GAMETYPES = (
    minqlxtended.Gametype.ATTACK_AND_DEFEND, minqlxtended.Gametype.CA,
    minqlxtended.Gametype.CTF, minqlxtended.Gametype.DOMINATION,
    minqlxtended.Gametype.FREEZE_TAG, minqlxtended.Gametype.TDM,
)
# Externally supported game types. Used by !getrating for game types the API works with.
EXT_SUPPORTED_GAMETYPES = SUPPORTED_GAMETYPES + (
    minqlxtended.Gametype.DUEL, minqlxtended.Gametype.FFA,
)

class balance(minqlxtended.Plugin):
    _qlx_balanceUseLocal = minqlxtended.setting("qlx_balanceUseLocal", True)
    _qlx_balanceLocalExpires = minqlxtended.setting("qlx_balanceLocalExpires", 0)
    _qlx_balanceUrl = minqlxtended.setting("qlx_balanceUrl", "qlstats.net")
    _qlx_balanceAuto = minqlxtended.setting("qlx_balanceAuto", True)
    _qlx_balanceMinimumSuggestionDiff = minqlxtended.setting("qlx_balanceMinimumSuggestionDiff", 25.0)
    _qlx_balanceMinimumSuggestionActionDiff = minqlxtended.setting("qlx_balanceMinimumSuggestionActionDiff", 50.0)
    _qlx_balanceApi = minqlxtended.setting("qlx_balanceApi", "elo")

    def __init__(self):
        super().__init__()

        self.ratings_lock = threading.RLock()
        # Keys: steam_id - Items: {"ffa": {"elo": 123, "games": 321, "local": False}, ...}
        self.ratings = {}
        self.player_info = {}
        self._current_map = ""
        # Keys: request_id - Items: (players, callback, channel)
        self.requests = {}
        self.request_counter = itertools.count()
        self.suggested_pair = None
        self.suggested_agree = [False, False]
        self.in_countdown = False
        self.suggestion_was_user_initiated = False

    @property
    def _api_url(self):
        return f"http://{self._qlx_balanceUrl}/{self._qlx_balanceApi}/"

    @minqlxtended.hook("round_countdown")
    def handle_round_countdown(self, round_number):
        self.in_countdown = True
        if self.suggested_pair and all(self.suggested_agree):
            # If we don't delay the switch a bit, the round countdown sound and
            # text disappears for some weird reason.
            @minqlxtended.next_frame
            def f():
                self.execute_suggestion()

            f()
        elif (any(self.suggested_agree)):
            for player, agreed in zip(self.suggested_pair, self.suggested_agree):
                if not agreed:
                    continue

                try:
                    player.update()
                except minqlxtended.NonexistentPlayerError:
                    self.suggested_pair = None
                    self.suggested_agree = [False, False]
                    return

            self.suggested_pair = None
            self.suggested_agree = [False, False]
        elif self.suggested_pair is not None:
            self.suggested_pair = None
            self.suggested_agree = [False, False]
        else:
            if not self._qlx_balanceAuto:
                return

            game = self.game
            if game is None:
                return

            gt = game.type_short
            if gt not in SUPPORTED_GAMETYPES:
                return

            teams = self.teams()
            if len(teams["red"]) != len(teams["blue"]):
                return

            wanted = dict([(p.steam_id, gt) for p in teams["red"] + teams["blue"]])
            if self.remove_cached(dict(wanted)):
                return

            self.add_request(wanted, self.callback_teams, minqlxtended.CHAT_CHANNEL, False)

    @minqlxtended.hook("round_start")
    def handle_round_start(self, round_number):
        self.in_countdown = False

    @minqlxtended.hook("vote_ended")
    def handle_vote_ended(self, votes, vote, args, passed):
        if passed and vote.lower() == "shuffle" and self._qlx_balanceAuto:
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

    @minqlxtended.hook("player_disconnect")
    def handle_player_disconnect(self, player, reason):
        self.clean_player_data(player)

    @minqlxtended.hook("new_game")
    def handle_new_game(self):
        game = self.game
        if game is None:
            return

        self._current_map = game.map

        # reset ratings cache on start
        if game.state == minqlxtended.GameState.WARMUP:
            with self.ratings_lock:
                self.ratings = {}

    def clean_player_data(self, player):
        for p in self.players():
            if p.steam_id == player.steam_id and p.id != player.id:
                # there is a second client with same steam id
                return

        with self.ratings_lock:
            self.player_info.pop(player.steam_id, None)
            self.ratings.pop(player.steam_id, None)

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
                local_elo = self.db.get(RATING_KEY.format(steam_id, gt))
                if local_elo is not None:
                    rating = {"games": -1, "elo": int(local_elo), "local": True, "time": -1}
                    with self.ratings_lock:
                        if steam_id in self.ratings:
                            self.ratings[steam_id][gt] = rating
                        else:
                            self.ratings[steam_id] = {gt: rating}
                    del players[steam_id]

            if not players:
                self.handle_ratings_fetched(request_id, requests.codes.ok)
                return

        attempts = 0
        last_status = 0
        untracked_sids = []

        current_map = self._current_map

        while attempts < MAX_ATTEMPTS:
            attempts += 1
            url = self._api_url + "+".join([str(sid) for sid in players])
            try:
                res = _session.get(url, headers={"X-QuakeLive-Map": current_map},
                                   timeout=BALANCE_TIMEOUT)
            except requests.RequestException:
                self.logger.exception("Failed to fetch ratings from the balance API.")
                last_status = -1
                continue
            last_status = res.status_code
            if res.status_code != requests.codes.ok:
                continue

            try:
                js = res.json()
            except ValueError:
                self.logger.exception("The balance API returned a body that isn't JSON.")
                last_status = -1
                continue

            if not isinstance(js, dict) or not isinstance(js.get("players"), list):
                last_status = -1
                continue

            # Fill our ratings dict with the ratings we just got.
            for p in js["players"]:
                try:
                    sid = int(p["steamid"])
                except (TypeError, ValueError, KeyError):
                    continue
                del p["steamid"]
                t = time.time()

                with self.ratings_lock:
                    if sid not in self.ratings:
                        self.ratings[sid] = {}

                    for gt in p:
                        if not isinstance(p[gt], dict) or "elo" not in p[gt] or "games" not in p[gt]:
                            continue
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

            try:
                untracked_sids = [int(sid) for sid in js.get("untracked", ())]
            except (TypeError, ValueError):
                last_status = -1
                continue

            for gt in SUPPORTED_GAMETYPES:
                for sid in untracked_sids:
                    with self.ratings_lock:
                        if sid not in self.ratings:
                            self.ratings[sid] = {}
                        self.ratings[sid][gt] = {"games": -1, "elo": UNTRACKED_RATING, "local": False, "time": time.time()}

            try:
                with self.ratings_lock:
                    for player, data in js.get("playerinfo", {}).items():
                        if not isinstance(data, dict):
                            continue
                        sid = int(player)
                        self.player_info[sid] = data
                        self.player_info[sid]["time"] = time.time()
            except (AttributeError, TypeError, ValueError):
                last_status = -1
                continue

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

    def rating(self, steam_id, gametype):
        """The cached rating for a player, or the default when the cache has none.

        handle_new_game empties self.ratings and clean_player_data pops from it, and
        either can land between a fetch and the callback it feeds. A missing entry
        degrades to the default rather than raising out of the frame task.
        """
        try:
            return self.ratings[steam_id][gametype]["elo"]
        except (KeyError, TypeError):
            return DEFAULT_RATING

    def remove_cached(self, players):
        with self.ratings_lock:
            for sid in players.copy():
                gt = players[sid]
                if sid in self.ratings and gt in self.ratings[sid]:
                    t = self.ratings[sid][gt]["time"]
                    if t == -1 or time.time() < t + CACHE_EXPIRE:
                        del players[sid]

        return players

    @minqlxtended.command(("getrating", "getelo", "elo"), usage="<id> [gametype]")
    def cmd_getrating(self, player, msg, channel):
        """Fetch the rating of the player ID supplied, or of the calling player if no ID supplied."""
        if len(msg) == 1:
            sid = player.steam_id
        else:
            resolved = self.resolve_identifier(msg[1], player)
            if resolved is None:
                return minqlxtended.Return.STOP_ALL
            sid = resolved.steam_id

        if len(msg) > 2:
            if msg[2].lower() in EXT_SUPPORTED_GAMETYPES:
                gt = msg[2].lower()
            else:
                player.tell(f"Invalid gametype. Supported gametypes: {', '.join(EXT_SUPPORTED_GAMETYPES)}")
                return minqlxtended.Return.STOP_ALL
        else:
            gt = self.game.type_short
            if gt not in EXT_SUPPORTED_GAMETYPES:
                player.tell("This game mode is not supported by the balance plugin.")
                return minqlxtended.Return.STOP_ALL

        self.add_request({sid: gt}, self.callback_getrating, channel, gt)

    def callback_getrating(self, players, channel, gametype):
        sid = next(iter(players))
        player = self.player(sid)
        if player:
            name = player.name
        else:
            name = sid

        channel.reply(f"{name}^7 has a rating of ^6{self.rating(sid, gametype)}^7 in {gametype.upper()}.")

    @minqlxtended.command(("setrating", "setelo"), permission=3, usage="<id> <rating>")
    def cmd_setrating(self, player, msg, channel):
        """Manually set the rating of a player. Depending on server configuration, this manually-set rating may expire after a pre-determined timeframe."""
        if len(msg) < 3:
            return minqlxtended.Return.USAGE

        resolved = self.resolve_identifier(msg[1], player)
        if resolved is None:
            return minqlxtended.Return.STOP_ALL
        sid, name, _ = resolved

        try:
            rating = int(msg[2])
        except ValueError:
            player.tell("Invalid rating.")
            return minqlxtended.Return.STOP_ALL

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

    @minqlxtended.command(("remrating", "remelo"), permission=3, usage="<id>")
    def cmd_remrating(self, player, msg, channel):
        """Remove a manually-set rating for a player."""
        if len(msg) < 2:
            return minqlxtended.Return.USAGE

        resolved = self.resolve_identifier(msg[1], player)
        if resolved is None:
            return minqlxtended.Return.STOP_ALL
        sid, name, _ = resolved

        gt = self.game.type_short

        try:
            del self.db[RATING_KEY.format(sid, gt)]
        except KeyError:
            channel.reply(f"{name}^7 does not have a locally set rating.")
            return minqlxtended.Return.STOP_ALL

        # If we have the player cached, remove the game type.
        with self.ratings_lock:
            if sid in self.ratings and gt in self.ratings[sid]:
                del self.ratings[sid][gt]

        channel.reply(f"{name}^7's locally set {gt.upper()} rating has been deleted.")

    @minqlxtended.command("balance", permission=1, client_cmd_perm=1)
    def cmd_balance(self, player, msg, channel):
        """Balance the teams according to player ratings, by distributing players evenly. Requires that the total number of players should be an even number."""
        gt = self.game.type_short
        if gt not in SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.Return.STOP_ALL

        teams = self.teams()
        if len(teams["red"] + teams["blue"]) % 2 != 0:
            player.tell("The total number of players should be an even number.")
            return minqlxtended.Return.STOP_ALL

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
                for i in range(diff // 2):
                    p = teams["red"].pop()
                    p.put("blue")
                    teams["blue"].append(p)
            elif diff < 0:
                for i in range(abs(diff) // 2):
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
                self.game.switch(p1, p2)
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

    @minqlxtended.command(("teams", "teens"))
    def cmd_teams(self, player, msg, channel):
        """Displays the current rating difference between teams."""
        gt = self.game.type_short
        if gt not in SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.Return.STOP_ALL

        teams = self.teams()
        if len(teams["red"]) != len(teams["blue"]):
            player.tell("Both teams should have the same number of players.")
            return minqlxtended.Return.STOP_ALL

        teams = dict([(p.steam_id, gt) for p in teams["red"] + teams["blue"]])
        self.add_request(teams, self.callback_teams, channel, True)

    def callback_teams(self, players, channel, user_initiated):
        # We check if people joined while we were requesting ratings and get them if someone did.
        teams = self.teams()
        current = teams["red"] + teams["blue"]
        gt = self.game.type_short

        for p in current:
            if p.steam_id not in players:
                d = dict([(p.steam_id, gt) for p in current])
                self.add_request(d, self.callback_teams, channel, user_initiated)
                return

        switch = self.suggest_switch(teams, gt)

        if user_initiated:
            avg_red = self.team_average(teams["red"], gt)
            avg_blue = self.team_average(teams["blue"], gt)
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
            if (switch[1] >= minimum_suggestion_action_diff) and (self.game.state == minqlxtended.GameState.IN_PROGRESS) and (not self.in_countdown):
                channel.reply(f"BALANCING: switching ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7 at the beginning of the next round.")
            elif (switch[1] >= minimum_suggestion_action_diff) and ((self.in_countdown) or (self.game.state != minqlxtended.GameState.IN_PROGRESS)):
                channel.reply(f"BALANCING: now switching ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7.")
            elif user_initiated:
                channel.reply(f"SUGGESTION: switch ^6{switch[0][0].clean_name}^7 with ^6{switch[0][1].clean_name}^7. Mentioned players can type !a to agree.")

            if (not self.suggested_pair) or (self.suggested_pair[0] != switch[0][0]) or (self.suggested_pair[1] != switch[0][1]):
                self.suggested_pair = (switch[0][0], switch[0][1])
                if (switch[1] >= minimum_suggestion_action_diff) and (self.game.state == minqlxtended.GameState.IN_PROGRESS) and (not self.in_countdown):
                    self.suggested_agree = [True, True]
                elif (switch[1] >= minimum_suggestion_action_diff) and ((self.in_countdown) or (self.game.state != minqlxtended.GameState.IN_PROGRESS)):
                    self.execute_suggestion()
                elif user_initiated:
                    self.suggested_agree = [False, False]
        else:
            if user_initiated:
                channel.reply("Teams look good!")
            self.suggested_pair = None
            self.suggested_agree = [False, False]

        return True

    @minqlxtended.command("do", permission=1)
    def cmd_do(self, player, msg, channel):
        """Forces a player switch as suggested by the balancer to be done."""
        if self.suggested_pair:
            self.execute_suggestion()

    @minqlxtended.command(("dl", "do_later"), permission=1, client_cmd_perm=1)
    def cmd_do_later(self, player, msg, channel):
        """Forces a player switch as suggested by the balancer to be done at the beginning of the next round."""
        if self.suggested_pair is not None:
            self.suggested_agree[0] = True
            self.suggested_agree[1] = True
            channel.reply("The switch will occur at the beginning of the next round.")
        else:
            channel.reply("There is no switch suggestion available to do later.")

    @minqlxtended.command(("agree", "a"), client_cmd_perm=0)
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
                if self.game.state == minqlxtended.GameState.IN_PROGRESS and not self.in_countdown:
                    self.msg("The switch will be executed at the start of next round.")
                    return

                # Otherwise, switch right away.
                self.execute_suggestion()

    @minqlxtended.command(("ratings", "elos", "selo", "egos"))
    def cmd_ratings(self, player, msg, channel):
        """List the ratings for each player, grouped by teams."""
        gt = self.game.type_short
        if gt not in EXT_SUPPORTED_GAMETYPES:
            player.tell("This game mode is not supported by the balance plugin.")
            return minqlxtended.Return.STOP_ALL

        players = dict([(p.steam_id, gt) for p in self.players()])
        self.add_request(players, self.callback_ratings, player.channel)
        return minqlxtended.Return.STOP_ALL

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
            free_sorted = sorted(teams["free"], key=lambda x: self.rating(x.steam_id, gt), reverse=True)
            free = ", ".join([f"{p.clean_name}: ^6{self.rating(p.steam_id, gt)}^7" for p in free_sorted])
            channel.reply(free)
        if teams["red"]:
            red_sorted = sorted(teams["red"], key=lambda x: self.rating(x.steam_id, gt), reverse=True)
            red = ", ".join([f"{p.clean_name}: ^1{self.rating(p.steam_id, gt)}^7" for p in red_sorted])
            channel.reply(red)
        if teams["blue"]:
            blue_sorted = sorted(teams["blue"], key=lambda x: self.rating(x.steam_id, gt), reverse=True)
            blue = ", ".join([f"{p.clean_name}: ^4{self.rating(p.steam_id, gt)}^7" for p in blue_sorted])
            channel.reply(blue)
        if teams["spectator"]:
            spec_sorted = sorted(teams["spectator"], key=lambda x: self.rating(x.steam_id, gt), reverse=True)
            spec = ", ".join([f"{p.clean_name}: {self.rating(p.steam_id, gt)}" for p in spec_sorted])
            channel.reply(spec)

    @minqlxtended.command("prepare", permission=1, client_cmd_perm=1)
    def cmd_prepare(self, player, msg, channel):
        """Shuffle and balance the teams."""
        self.game.shuffle()
        return self.cmd_balance(player, msg, channel)

    @minqlxtended.vote("balance", description="Balances the teams using the glicko algorithm.")
    def vote_balance(self, caller, args):
        teams = self.teams()
        if ((len(teams["red"]) + len(teams["blue"])) % 2 != 0) or ((len(teams["red"]) + len(teams["blue"])) == 0):
            caller.tell("Voting to balance isn't possible while the number of players across both teams is uneven.")
            caller.tell(
                f"There are ^1{len(teams['red'])}^7 player{'s' if len(teams['red']) != 1 else ''} on red, and ^4{len(teams['blue'])}^7 player{'s' if len(teams['blue']) != 1 else ''} on blue."
            )
            return None

        return minqlxtended.CustomVote("balance the teams", self._start_balance)

    @minqlxtended.vote("do", usage="[now/later]", description="Forces the suggested switch now, or at the start of the next round.")
    def vote_do(self, caller, args):
        args = args.strip().lower()
        if len(args) <= 1:
            caller.tell("Please use one of the following options:")
            caller.tell("  ^2/cv do later^7 forces the switch at the beginning of the next round.")
            caller.tell("  ^2/cv do now^7 forces the switch at the end of the vote.")
            return None

        if not self.suggested_pair:
            caller.tell("A switch hasn't been suggested yet by ^6!teams^7, a suggestion is required before ^2do^7 can execute.")
            return None

        if args == "now":
            return minqlxtended.CustomVote("force the suggested switch now", self._execute_do_now)
        if args == "later":
            return minqlxtended.CustomVote("force the suggested switch at the start of the next round", self._execute_do_later)

        caller.tell("You have specified an invalid argument, either ^2now^7 or ^2later^7 are accepted arguments.")
        return None

    @minqlxtended.vote("go", description="Balances and begins the game.")
    def vote_go(self, caller, args):
        if self.game.state != minqlxtended.GameState.WARMUP:
            caller.tell("Voting to go is not permitted during an active game.")
            return None

        return minqlxtended.CustomVote("balance the teams and begin the game", self._execute_go)

    def _start_balance(self):
        """Balance the full teams to chat. Runs when /cv balance or /cv go passes."""
        gt = self.game.type_short
        if gt not in SUPPORTED_GAMETYPES:
            self.msg("This game mode is not supported by the balance plugin.")
            return

        teams = self.teams()
        if len(teams["red"] + teams["blue"]) % 2 != 0:
            self.msg("The teams were not balanced; the total number of players is no longer even.")
            return

        players = dict([(p.steam_id, gt) for p in teams["red"] + teams["blue"]])
        self.add_request(players, self.callback_balance, minqlxtended.CHAT_CHANNEL)

    def _execute_do_now(self):
        if self.suggested_pair:
            self.execute_suggestion()

    def _execute_do_later(self):
        if self.suggested_pair is None:
            return

        self.suggested_agree[0] = True
        self.suggested_agree[1] = True
        self.msg("The switch will occur at the beginning of the next round.")

    def _execute_go(self):
        self._start_balance()
        game = self.game
        if game is not None and game.state == minqlxtended.GameState.WARMUP:
            game.allready()

    def suggest_switch(self, teams, gametype):
        """Suggest a switch based on average team ratings.

        Called in a loop from the balance paths, on the game thread, at every round
        countdown. Swapping one player for another only moves two ratings between the
        sums, so the difference a candidate pair would leave is

            |(R - a + b)/nr - (B - b + a)/nb|

        over sums computed once.
        """
        red = teams["red"]
        blue = teams["blue"]
        if not red or not blue:
            return None

        red_elos = [self.rating(p.steam_id, gametype) for p in red]
        blue_elos = [self.rating(p.steam_id, gametype) for p in blue]

        nr = len(red)
        nb = len(blue)
        red_sum = sum(red_elos)
        blue_sum = sum(blue_elos)

        cur_diff = abs(red_sum / nr - blue_sum / nb)

        min_diff = cur_diff
        best_pair = None

        for i, a in enumerate(red_elos):
            red_without = red_sum - a
            blue_with = blue_sum + a
            for j, b in enumerate(blue_elos):
                diff = abs((red_without + b) / nr - (blue_with - b) / nb)
                if diff < min_diff:
                    min_diff = diff
                    best_pair = (red[i], blue[j])

        if best_pair is None:
            return None

        return (best_pair, cur_diff - min_diff)

    def team_average(self, team, gametype):
        """Calculates the average rating of a team."""
        avg = 0
        if team:
            for p in team:
                avg += self.rating(p.steam_id, gametype)
            avg /= len(team)

        return avg

    def execute_suggestion(self):
        if not self.suggested_pair:
            return

        p1, p2 = self.suggested_pair
        try:
            p1.update()
            p2.update()
        except minqlxtended.NonexistentPlayerError:
            self.suggested_pair = None
            self.suggested_agree = [False, False]
            return

        if p1.team != minqlxtended.Team.SPECTATOR and p2.team != minqlxtended.Team.SPECTATOR:
            p1stats, p1score = p1.stats, p1.score
            p2stats, p2score = p2.stats, p2.score
            self.game.switch(p1, p2)

            @minqlxtended.delay(1)
            def f(p1, p2, p1stats, p2stats, p1score, p2score):
                p1.stats, p1.score = p1stats, p1score
                p2.stats, p2.score = p2stats, p2score

            f(p1, p2, p1stats, p2stats, p1score, p2score)

        self.suggested_pair = None
        self.suggested_agree = [False, False]
