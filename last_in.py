# Copyright (c) 2024 Thomas Jones <me@thomasjones.id.au>
# This file is part of minqlxtended.

import minqlxtended

SUPPORTED_GAMETYPES = ("ad", "ca", "ctf", "dom", "ft", "tdm")

class last_in(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("team_switch", self.handle_team_switch, priority=minqlxtended.PRI_LOW)
        self.add_hook("team_switch_attempt", self.handle_team_switch_attempt, priority=minqlxtended.PRI_HIGH)
        self.add_command("lastin", self.cmd_last_in, client_cmd_perm=0)
        self.add_command(("c", "count"), self.cmd_count, client_cmd_perm=0)

        self.last_players_in = {"red": False, "blue": False}
        self.transitioning_players = []


    @minqlxtended.next_frame
    def handle_team_switch(self, player, old_team, new_team):
        if player in self.transitioning_players:
            self.transitioning_players.remove(player)
            self.last_players_in[new_team] = player

    def handle_team_switch_attempt(self, player, old_team, new_team):
        if not new_team.lower().startswith("s"):
            self.transitioning_players.append(player)

    def cmd_last_in(self, player, msg, channel):
        """ Display the last players who joined the blue/red team. """
        if self.game.type_short not in SUPPORTED_GAMETYPES:
            channel.reply(f"The ^6{self.game.type_short.upper()}^7 game type is not supported by this command.")
            return

        red_msg, red_id = self.get_player_string(self.last_players_in["red"], "red")
        blue_msg, blue_id = self.get_player_string(self.last_players_in["blue"], "blue")
        
        if self.db.has_permission(player, 2):  # display more information (player ID, etc)
            channel.reply(f"Red: (^6{red_id}^7) ^1{red_msg}^7 ^6|^7 Blue: (^6{blue_id}^7) ^4{blue_msg}^7")
        else:
            channel.reply(f"Red: ^1{red_msg}^7 ^6|^7 Blue: ^4{blue_msg}^7")

    def cmd_count(self, player, msg, channel):
        """Lists the count of players on each team. Useful for when the scoreboard is exceeded."""
        teams = self.teams()
        is_team_game = self.get_cvar("g_gametype", int) >= 3
        if is_team_game:
            channel.reply(f"^1RED TEAM: {len(teams['red'])} ^6|^4 BLUE TEAM: {len(teams['blue'])} ^6|^7 SPECTATORS: {len(teams['spectator'])}")
        else:
            channel.reply(f"^4IN-GAME: {len(teams['free'])} ^6|^7 SPECTATORS: {len(teams['spectator'])}")

    def get_player_string(self, player, team):
        if (player == False):
            return "Not recorded yet.", "No ID"

        try:
            player.update()
        except minqlxtended.NonexistentPlayerError:
            return f"{player.clean_name} ^3(disconnected)", "No ID"

        if (not player.valid):
            return f"{player.clean_name} ^3(disconnected)", "No ID"

        if (player.team != team):
            return f"{player.clean_name} ^3(left team)", player.id

        return player.clean_name, player.id


    
