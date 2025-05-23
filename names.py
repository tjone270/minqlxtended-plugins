# minqlx - Extends Quake Live's dedicated server with extra functionality and scripting.
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
import re

_re_remove_excessive_colors = re.compile(r"(?:\^.)+(\^.)")
_name_key = "minqlx:players:{}:colored_name"

class names(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("player_disconnect", self.handle_player_disconnect)
        self.add_hook("userinfo", self.handle_userinfo)
        self.add_command(("name", "setname"), self.cmd_name, usage="<name>", client_cmd_perm=0)

        self.set_cvar_once("qlx_enforceSteamName", "1")
        
        self.steam_names = {}
        self.name_set = False

        self._cache_variables()

    def _cache_variables(self):
        """ we do this to prevent lots of unnecessary engine calls """
        self._qlx_enforceSteamName = self.get_cvar("qlx_enforceSteamName", bool)
        self._qlx_commandPrefix = self.get_cvar("qlx_commandPrefix")

    def handle_player_connect(self, player):
        self.steam_names[player.steam_id] = player.clean_name
    
    def handle_player_loaded(self, player):
        name_key = _name_key.format(player.steam_id)
        if name_key in self.db:
            db_name = self.db[name_key]
            if not self._qlx_enforceSteamName or self.clean_text(db_name).lower() == player.clean_name.lower():
                self.name_set = True
                player.name = db_name

    def handle_player_disconnect(self, player, reason):
        if player.steam_id in self.steam_names:
            del self.steam_names[player.steam_id]

    def handle_userinfo(self, player, changed):
        # Make sure we're not doing anything if our script set the name.
        if self.name_set:
            self.name_set = False
            return

        if "name" in changed:
            name_key = _name_key.format(player.steam_id)
            if name_key not in self.db:
                self.steam_names[player.steam_id] = self.clean_text(changed["name"])
            elif self.steam_names[player.steam_id] == self.clean_text(changed["name"]):
                changed["name"] = self.db[name_key]
                return changed
            else:
                del self.db[name_key]
                player.tell("Your registered name has been reset.")

    def cmd_name(self, player, msg, channel):
        """ Re-colours the player's name to the string specified, or clears custom colouring if nothing specified. """
        name_key = _name_key.format(player.steam_id)
        
        if len(msg) < 2:
            if name_key not in self.db:
                return minqlxtended.RET_USAGE
            else:
                del self.db[name_key]
                player.tell("Your registered name has been removed.")
                return minqlxtended.RET_STOP_ALL
        
        name = self.clean_excessive_colors(" ".join(msg[1:]))
        if len(name.encode()) > 36:
            player.tell("The name is too long. Consider using fewer colors or a shorter name.")
            return minqlxtended.RET_STOP_ALL
        elif self.clean_text(name).lower() != player.clean_name.lower() and self._qlx_enforceSteamName:
            player.tell("The new name must match your current Steam name.")
            return minqlxtended.RET_STOP_ALL
        elif "\\" in name:
            player.tell("The character '^6\\^7' cannot be used. Sorry for the inconvenience.")
            return minqlxtended.RET_STOP_ALL
        elif not self.clean_text(name).strip():
            player.tell("Blank names cannot be used. Sorry for the inconvenience.")
            return minqlxtended.RET_STOP_ALL

        self.name_set = True
        name = "^7" + name
        player.name = name
        self.db[name_key] = name
        player.tell(f"The name has been registered. To make me forget about it, a simple ^6{self._qlx_commandPrefix}name^7 will do it.")
        return minqlxtended.RET_STOP_ALL

    def clean_excessive_colors(self, name):
        """Removes excessive colors and only keeps the ones that matter."""
        def sub_func(match):
            return match.group(1)

        return _re_remove_excessive_colors.sub(sub_func, name)

