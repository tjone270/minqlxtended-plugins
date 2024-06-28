# Copyright (c) 2024 Thomas Jones <me@thomasjones.id.au>
# This file is part of minqlxtended.

import minqlxtended

SUPPORTED_GAMETYPES = ("ad", "ca", "ctf", "dom", "ft", "tdm")

class last_in(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("team_switch", self.handle_team_switch, priority=minqlxtended.PRI_LOW)
        self.add_hook("client_command", self.handle_client_command, priority=minqlxtended.PRI_HIGH)
        self.add_hook("new_game", self.handle_new_game)
        self.add_hook("map", self.handle_map)
        self.add_command("lastin", self.cmd_last_in)

        self.last_players_in = {"red": False, "blue": False}
        self.transitioning_players = []


    @minqlxtended.next_frame
    def handle_team_switch(self, player, old_team, new_team):
        if player in self.transitioning_players:
            self.transitioning_players.remove(player)
            self.last_players_in[new_team] = player

    def handle_client_command(self, player, cmd):
        cmd = cmd.lower().split(" ")
        
        if (cmd[0] != "team") or (not player.valid):
            return
        else:
            team = cmd[1]

        if (team == "a") or (team == "b") or (team == "r"):
            self.transitioning_players.append(player)

    def handle_new_game(self, *args, **kwargs):
        self.last_players_in = {"red": False, "blue": False}
        self.transitioning_players = []

    def handle_map(self, *args, **kwargs):
        self.last_players_in = {"red": False, "blue": False}
        self.transitioning_players = []

    def cmd_last_in(self, player, msg, channel):
        """ Display the last player who joined whichever team. """
        if self.game.type_short not in SUPPORTED_GAMETYPES:
            channel.reply("The ^6{}^7 game type is not supported by this command.".format(self.game.type_short.upper()))
            return

        red_msg, red_id = self.get_player_string(self.last_players_in["red"], "red")
        blue_msg, blue_id = self.get_player_string(self.last_players_in["blue"], "blue")
        
        if self.db.has_permission(player, 2):  # display more information (player ID, etc)
            channel.reply("Red: (^6{}^7) ^1{}^7 ^6|^7 Blue: (^6{}^7) ^4{}^7".format(red_id, red_msg, blue_id, blue_msg))
        else:
            channel.reply("Red: ^1{}^7 ^6|^7 Blue: ^4{}^7".format(red_msg, blue_msg))

    def get_player_string(self, player, team):
        if (player == False):
            return "Not recorded yet.", "No ID"

        try:
            player.update()
        except minqlxtended.NonexistentPlayerError:
            return "{} ^3(disconnected)".format(player.clean_name), "No ID"

        if (not player.valid):
            return "{} ^3(disconnected)".format(player.clean_name), "No ID"

        if (player.team != team):
            return "{} ^3(left team)".format(player.clean_name), player.id

        return player.clean_name, player.id


    
