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

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

class workshop(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("map", self.handle_map)

        self.set_cvar_once("qlx_workshopReferences", "")

    def handle_map(self, *args, **kwargs):
        # Reference our custom workshop items. get_cvar(..., list) turns an empty cvar into [''],
        # so filter out blank entries before extending the workshop list.
        references = [item for item in self.get_cvar("qlx_workshopReferences", list) if item]
        if references:
            self.game.workshop_items += references
