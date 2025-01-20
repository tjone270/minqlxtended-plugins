# Created by Thomas Jones on 26/07/2017 - thomas@tomtecsolutions.com
# sv_fps.py, a plugin for minqlx to modify the previously unmodifiable sv_fps cvar.
# This plugin is released to everyone, for any purpose. It comes with no warranty, no guarantee it works, it's released AS IS.
# You can modify everything, except for lines 1-4 and the !tomtec_versions code. They're there to indicate I whacked this together originally. Please make it better :D

# modified 12/01/2025 to make compatible with minqlxtended

import minqlxtended

STD_SVFPS = 40
class sv_fps(minqlxtended.Plugin):
    def __init__(self):
        self.add_command(("sv_fps", "svfps"), self.cmd_svfps, 5, usage="<integer>")
        self.add_command("tomtec_versions", self.cmd_showversion)
        self.set_cvar_once("qlx_svfps", str(STD_SVFPS))
        self.plugin_version = "1.3"
        self.set_initial_fps(self.get_cvar("qlx_svfps", int))

        
    def cmd_svfps(self, player, msg, channel):
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            sv_fps = int(msg[1])
        except ValueError:
            channel.reply(f"You must specify a positive integer greater than or equal to {STD_SVFPS}.")
            return minqlxtended.RET_STOP

        if (self.check_value(sv_fps, channel)):
            minqlxtended.set_cvar("sv_fps", str(sv_fps), -1)
            channel.reply(f"sv_fps is now set to {sv_fps}.")

    @minqlxtended.delay(5)
    def set_initial_fps(self, cvarval):
        if (cvarval != STD_SVFPS):
            if (self.check_value(cvarval, minqlxtended.CHAT_CHANNEL)):
                minqlxtended.set_cvar("sv_fps", str(cvarval), -1)
            else:
                self.msg("Will not set sv_fps to value of qlx_svfps as the latter contains an incompatible value.")
        else:
            pass 
        
    def check_value(self, sv_fps, channel):
        ret = True
        if (sv_fps < 0):
            channel.reply("The integer specified must be positive.")
            ret = False
        if (sv_fps < STD_SVFPS):
            channel.reply(f"The integer specified must not be less than the preset sv_fps value ({STD_SVFPS})")
            ret = False
        if ((sv_fps % STD_SVFPS) != 0):
            channel.reply(f"The integer specified must be divisible by {STD_SVFPS}. ({STD_SVFPS*2}, {STD_SVFPS*3}, {STD_SVFPS*4}, {STD_SVFPS*5} etc)")
            ret = False
        return ret

    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4sv_fps.py^7 - version {self.plugin_version}, created by Thomas Jones on 26/07/2017.")
