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

"""
A plugin that allows a race server to start and keep a game going even without having
a minimum of two players on a server, like you usually do.
"""

import minqlxtended

class solorace(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("team_switch", self.handle_team_switch)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("new_game", self.handle_new_game)

    def handle_team_switch(self, player, old_team, new_team):
        if (self.game.type_short == "race") and (old_team == "free") and (self.game.state == "in_progress") and (not self.teams()["free"]):
            minqlxtended.console_command("map_restart")
    
    def handle_player_disconnect(self, player, reason):
        if (len(self.teams()["free"]) == 1) and (player.team == "free"):
            minqlxtended.console_command("map_restart")

    def handle_new_game(self):
        if self.game.type_short == "race":
            self.set_cvar("g_doWarmup", "0")
            minqlxtended.allow_single_player(True)
        else:
            self.set_cvar("g_doWarmup", "1")
