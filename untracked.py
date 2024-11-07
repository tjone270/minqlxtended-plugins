# untracked.py - a plugin for minqlxtended to prevent untrackable players from engaging in a match.

# Created 07/11/2024.

import minqlxtended
import requests

ACTION_PREVENT_TEAM_CHANGE = 1
ACTION_PREVENT_PLAYER_CONNECTION = 2

PLAYER_CONNECTION_MESSAGE = "Untrackable players are ^1not allowed^7 to connect to this server.\n"
PLAYER_DISALLOW_GAMEPLAY_MESSAGE = "Untrackable players are ^1not allowed^7 to join the match."

class untracked(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("new_game", self._cache)
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("team_switch_attempt", self.handle_team_switch)
        self.add_hook("team_switch", self.handle_team_switch)

        self.set_cvar_once("qlx_untrackedPlayerAction", "0") # 0 = do nothing, 1 = prevent player team changes, 2 = prevent player connection

        self._cache()


    def _cache(self):
        self._balance_loaded = ("balance" in self.plugins)
        self._untracked_player_action = self.get_cvar("qlx_untrackedPlayerAction", int)
        
        self.tracked_players = set()
        self.untracked_players = set()
        
        if self._balance_loaded:
            self._api_url = self.plugins["balance"]._api_url

    def handle_player_connect(self, player): # initial connection event
        if (self._balance_loaded):
            if (player.steam_id in self.untracked_players) and (self._untracked_player_action == ACTION_PREVENT_PLAYER_CONNECTION):
                return PLAYER_CONNECTION_MESSAGE
            
            self.check_player_trackable(player, self.handle_untracked_player)

    @minqlxtended.next_frame
    def handle_player_loaded(self, player): # fires when clients re-prime after map change etc, along with initial game join
        if (self._balance_loaded):
            self.check_player_trackable(player, self.handle_untracked_player)

            if (player.steam_id in self.untracked_players) and (self._untracked_player_action == ACTION_PREVENT_PLAYER_CONNECTION):
                self.msg(f"^1Untrackable Player^7: {player.name}^7 is not QLStats trackable, their connection is blocked.")
            elif (player.steam_id in self.untracked_players) and (self._untracked_player_action == ACTION_PREVENT_TEAM_CHANGE):
                self.msg(f"^1Untrackable Player^7: {player.name}^7 is not QLStats trackable, they cannot join the match.")
            else:
                self.msg(f"^1Untrackable Player^7: {player.name}^7 is not QLStats trackable.")

    def handle_team_switch(self, player, _, new_team):
        if new_team == "spectator": 
            return
        
        if (player.steam_id in self.untracked_players) and (self._untracked_player_action >= ACTION_PREVENT_TEAM_CHANGE):
            if player.team != "spectator":
                player.team = "spectator"

            player.tell(PLAYER_DISALLOW_GAMEPLAY_MESSAGE)
            return minqlxtended.RET_STOP_ALL

    def handle_untracked_player(self, player):
        if player.valid and player.connection_state == "active":
            if self._untracked_player_action == ACTION_PREVENT_PLAYER_CONNECTION:
                player.kick(self.clean_text(PLAYER_DISALLOW_GAMEPLAY_MESSAGE))
            elif self._untracked_player_action == ACTION_PREVENT_TEAM_CHANGE:
                if player.team != "spectator":
                    player.team = "spectator"

                player.tell(PLAYER_DISALLOW_GAMEPLAY_MESSAGE)

    @minqlxtended.thread
    def check_player_trackable(self, player, callback_untracked) -> bool:
        if player.is_bot or player.steam_id in self.tracked_players: # skip bots and pre-validated players.
            return
        
        if player.steam_id in self.untracked_players: # kick the arse of the existing ones.
            callback_untracked(player)
        
        url = f"{self._api_url}{player.steam_id}"
        res = requests.get(url, headers={"X-QuakeLive-Map": self.game.map})
        if res.status_code == requests.codes.ok:
            data = res.json()            
            if str(player.steam_id) in data["untracked"]:
                self.untracked_players.add(player.steam_id)
                return callback_untracked(player)
        
        self.tracked_players.add(player.steam_id) # prevent future requests by caching the result per-game
