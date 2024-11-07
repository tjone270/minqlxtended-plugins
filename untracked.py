# untracked.py - a plugin for minqlxtended to prevent untrackable players from engaging in a match.

# Created 07/11/2024.

import minqlxtended
import requests

ACTION_PREVENT_TEAM_CHANGE = 1
ACTION_PREVENT_PLAYER_CONNECTION = 2

PLAYER_CONNECTION_MESSAGE = "Untrackable players are ^1not allowed^7 to connect to this server."
PLAYER_TEAM_CHANGE_MESSAGE = "Untrackable players are ^1not allowed^7 to join the match."

class untracked(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("new_game", self.handle_new_game)
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("team_switch_attempt", self.handle_team_switch_attempt)

        self.set_cvar_once("qlx_untrackedPlayerAction", "0") # 0 = do nothing, 1 = prevent player team changes, 2 = prevent player connection

        self.untracked_players = set()
        self._cache_cvars()


    def _cache_cvars(self):
        self._balance_loaded = ("balance" in self.plugins)
        self._untracked_player_action = self.get_cvar("qlx_untrackedPlayerAction", int)
        if self._balance_loaded:
            self._api_url = self.plugins["balance"]._api_url
        
    def handle_new_game(self):
        self._cache_cvars()
        self.untracked_players = set()

    def handle_player_connect(self, player):
        if (self._balance_loaded) and (self._untracked_player_action == ACTION_PREVENT_PLAYER_CONNECTION):
            if self.is_player_tracked(player):
                return PLAYER_CONNECTION_MESSAGE

    def handle_team_switch_attempt(self, player, old_team, new_team):
        if (self._balance_loaded) and (self._untracked_player_action == ACTION_PREVENT_TEAM_CHANGE):
            if self.is_player_tracked(player):
                player.tell(PLAYER_TEAM_CHANGE_MESSAGE)
                player.center_print(PLAYER_TEAM_CHANGE_MESSAGE)
                return minqlxtended.RET_STOP_ALL

    # not threaded, so runs in the main thread - had better be quick!
    def is_player_tracked(self, player) -> bool:
        if player.steam_id in self.untracked_players:
            return True
        
        url = f"{self._api_url}{player.steam_id}"
        res = requests.get(url, headers={"X-QuakeLive-Map": self.game.map})
        if res.status_code != requests.codes.ok:
            return False # fail open
        
        data = res.json()            
        if len(data["untracked"]) > 0:
            self.untracked_players.add(player.steam_id)
            return True
