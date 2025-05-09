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
from os.path import basename

MOTD_SET_KEY = "minqlx:motd"

class motd(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("player_loaded", self.handle_player_loaded, priority=minqlxtended.PRI_LOWEST)
        self.add_command(("setmotd", "newmotd"), self.cmd_setmotd, 4, usage="<motd>")
        self.add_command(("setmotdall", "newmotdall"), self.cmd_setmotdall, 4, usage="<motd>")
        self.add_command(("getmotd", "motd"), self.cmd_getmotd)
        self.add_command(("clearmotd", "removemotd", "remmmotd"), self.cmd_clearmotd, 4)
        self.add_command(("clearmotdall", "removemotdall", "remmmotdall"), self.cmd_clearmotdall, 4)
        self.add_command("addmotd", self.cmd_addmotd, 4, usage="<more_motd>")
        self.add_command("addmotdall", self.cmd_addmotdall, 4, usage="<more_motd>")

        # homepath doesn't change runtime, so we can just save it for the sake of efficiency.
        self.home = basename(self.get_cvar("fs_homepath"))
        self.motd_key = f"{MOTD_SET_KEY}:{self.home}"

        # Add this server to the MOTD set.
        self.db.sadd(MOTD_SET_KEY, self.home)

        # Cvar to disable/change the welcome sound.
        self.set_cvar_once("qlx_motdSound", "sound/vo/crash_new/37b_07_alt.wav")
        self.set_cvar_once("qlx_motdHeader", "^6======= ^7Message of the Day ^6=======^7")

        self._cache_variables()


    def _cache_variables(self):
        """ we do this to prevent lots of unnecessary engine calls """
        self._qlx_motdSound = self.get_cvar("qlx_motdSound")
        self._qlx_motdHeader = self.get_cvar("qlx_motdHeader")

    @minqlxtended.delay(2)
    def handle_player_loaded(self, player):
        """Send the message of the day to the player in a tell.

        This should be set to lowest priority so that we don't execute anything if "ban" or
        a similar plugin determines the player should be kicked.
        """
        try:
            motd = self.db[self.motd_key]
        except KeyError:
            return
        
        welcome_sound = self._qlx_motdSound
        if welcome_sound == "0":
            welcome_sound = ""
        
        if welcome_sound and self.db.get_flag(player, "essentials:sounds_enabled", default=True):
            self.play_sound(welcome_sound, player)
        self.send_motd(player, motd)

    def cmd_setmotd(self, player, msg, channel):
        """ Set the message of the day for this server to the one specified. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        self.db.sadd(MOTD_SET_KEY, self.home)
        self.db[self.motd_key] = " ".join(msg[1:])
        player.tell("The MOTD has been set.")
        return minqlxtended.RET_STOP_EVENT

    def cmd_setmotdall(self, player, msg, channel):
        """ Set the message of the day for all servers to the one specified. """
        motds = self.db.smembers(MOTD_SET_KEY)
        db = self.db.pipeline()
        for path in motds:
            motd_key = f"{MOTD_SET_KEY}:{path}"
            db.set(motd_key, " ".join(msg[1:]))
        db.execute()
        player.tell("All MOTDs have been set.")
        return minqlxtended.RET_STOP_EVENT
    
    def cmd_getmotd(self, player, msg, channel):
        """ Shows the current message of the day for this server. """
        if self.motd_key in self.db:
            self.send_motd(player, self.db[self.motd_key])
        else:
            player.tell("No MOTD has been set.")
        return minqlxtended.RET_STOP_EVENT

    def cmd_clearmotd(self, player, msg, channel):
        """ Clears the message of the day on this server. """
        del self.db[self.motd_key]
        player.tell("The MOTD has been cleared.")
        return minqlxtended.RET_STOP_EVENT

    def cmd_clearmotdall(self, player, msg, channel):
        """ Clears the message of the day on all servers. """
        motds = [f"{MOTD_SET_KEY}:{m}" for m in self.db.smembers(MOTD_SET_KEY)]
        self.db.delete(*motds)
        player.tell("All MOTDs have been cleared.")
        return minqlxtended.RET_STOP_EVENT

    def cmd_addmotd(self, player, msg, channel):
        """ Appends the specified text to the existing message of the day on this server. """
        motd = self.db[self.motd_key]
        if not motd:
            self.db[self.motd_key] = " ".join(msg[1:])
            player.tell("No MOTD was set, so a new one was made.")
        else:
            leading_space = "" if len(motd) > 2 and motd[-2:] == "\\n" else " "
            self.db[self.motd_key] = motd + leading_space + " ".join(msg[1:])
            player.tell("The MOTD has been updated.")

        return minqlxtended.RET_STOP_EVENT

    def cmd_addmotdall(self, player, msg, channel):
        """ Appends the specified text to the existing message of the day on all servers. """
        motds = self.db.smembers(MOTD_SET_KEY)
        for path in motds:
            motd_key = f"{MOTD_SET_KEY}:{path}"
            if motd_key not in self.db:
                self.db[motd_key] = " ".join(msg[1:])
            else:
                motd = self.db[motd_key]
                leading_space = "" if len(motd) > 2 and motd[-2:] == "\\n" else " "
                self.db[motd_key] = motd + leading_space + " ".join(msg[1:])
        player.tell("Added to all MOTDs.")
        return minqlxtended.RET_STOP_EVENT

    def send_motd(self, player, motd):
        for line in self._qlx_motdHeader.split("\\n"):
            player.tell(line)
        for line in motd.split("\\n"):
            player.tell(line)

