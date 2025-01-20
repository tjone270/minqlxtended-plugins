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

class plugin_manager(minqlxtended.Plugin):
    def __init__(self):
        self.add_command("load", self.cmd_load, 5, usage="<plug-in>")
        self.add_command("unload", self.cmd_unload, 5, usage="<plug-in>")
        self.add_command("reload", self.cmd_reload, 5, usage="<plug-in>")
        self.add_command("loadall", self.cmd_loadall, 5)
        self.add_command("unloadall", self.cmd_unloadall, 5)
        self.add_command("reloadall", self.cmd_reloadall, 5)
    
    def cmd_load(self, player, msg, channel):
        """ Loads the specified plug-in (omitting the file extension.) """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        else:
            try:
                minqlxtended.load_plugin(msg[1])
                channel.reply(f"Plug-in ^6{msg[1]}^7 has been successfully loaded.")
            except Exception as e:
                channel.reply(f"Plug-in ^6{msg[1]}^7 has failed to load:")
                channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                minqlxtended.log_exception(self)
    
    def cmd_unload(self, player, msg, channel):
        """ Unloads the specified plug-in. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        else:
            try:
                minqlxtended.unload_plugin(msg[1])
                channel.reply(f"Plug-in ^6{msg[1]}^7 has been successfully unloaded.")
            except Exception as e:
                channel.reply(f"Plug-in ^6{msg[1]}^7 has failed to unload:")
                channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                minqlxtended.log_exception(self)
    
    def cmd_reload(self, player, msg, channel):
        """ Reloads the specified plug-in. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        else:
            # Wrap in next_frame to avoid the command going off several times due
            # to the plugins dict being modified mid-command execution.
            @minqlxtended.next_frame
            def f():
                try:
                    minqlxtended.reload_plugin(msg[1])
                    channel.reply(f"Plug-in ^6{msg[1]}^7 has been successfully reloaded.")
                except Exception as e:
                    channel.reply(f"Plug-in ^6{msg[1]}^7 has failed to reload:")
                    channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                    minqlxtended.log_exception(self)

            f()

    def cmd_loadall(self, player, msg, channel):
        """ Loads all plug-ins specified in the qlx_plugins CVAR. """
        # Wrap in next_frame to avoid the command going off several times due
        # to the plugins dict being modified mid-command execution.
        @minqlxtended.next_frame
        def f():
            try:
                minqlxtended.load_preset_plugins()
            except Exception as e:
                channel.reply("Plug-ins failed to load:")
                channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                minqlxtended.log_exception(self)

            channel.reply("Successfully loaded all plug-ins in ^6qlx_plugins^7.")
        f()

    def cmd_unloadall(self, player, msg, channel):
        """ Unloads all plug-ins currently loaded (except the 'plugin_manager' plug-in.) """
        for plugin in self.plugins:
            if plugin != self.__class__.__name__:
                try:
                    minqlxtended.unload_plugin(plugin)
                except Exception as e:
                    channel.reply(f"Plug-in ^6{plugin}^7 failed to unload:")
                    channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                    minqlxtended.log_exception(self)

        channel.reply(f"Successfully unloaded all plug-ins except {self.__class__.__name__}.")

    def cmd_reloadall(self, player, msg, channel):
        """ Reloads all plug-ins currently loaded (except the 'plugin_manager' plug-in.) """
        # Wrap in next_frame to avoid the command going off several times due
        # to the plugins dict being modified mid-command execution.
        @minqlxtended.next_frame
        def f():
            for plugin in self.plugins:
                if plugin != self.__class__.__name__:
                    try:
                        minqlxtended.reload_plugin(plugin)
                    except Exception as e:
                        channel.reply(f"Plug-in ^6{plugin}^7 failed to reload:")
                        channel.reply(f"^1{e.__class__.__name__}^7: {e}")
                        minqlxtended.log_exception(self)

            channel.reply(f"Successfully reloaded all plug-ins except {self.__class__.__name__}.")

        f()
