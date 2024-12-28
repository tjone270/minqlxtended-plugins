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
                channel.reply("Plug-in ^6{} ^7has been successfully loaded."
                    .format(msg[1]))
            except Exception as e:
                channel.reply("Plug-in ^6{} ^7has failed to load: {} - {}"
                    .format(msg[1], e.__class__.__name__, e))
                minqlxtended.log_exception(self)
    
    def cmd_unload(self, player, msg, channel):
        """ Unloads the specified plug-in. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        else:
            try:
                minqlxtended.unload_plugin(msg[1])
                channel.reply("Plug-in ^6{} ^7has been successfully unloaded."
                    .format(msg[1]))
            except Exception as e:
                channel.reply("Plug-in ^6{} ^7has failed to unload: {} - {}"
                    .format(msg[1], e.__class__.__name__, e))
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
                    channel.reply("Plug-in ^6{} ^7has been successfully reloaded."
                        .format(msg[1]))
                except Exception as e:
                    channel.reply("Plug-in ^6{} ^7has failed to reload: {} - {}"
                        .format(msg[1], e.__class__.__name__, e))
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
                channel.reply("Plug-ins failed to load: {} - {}"
                    .format(e.__class__.__name__, e))
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
                    channel.reply("Plug-in ^6{} ^7has failed to unload: {} - {}"
                        .format(plugin, e.__class__.__name__, e))
                    minqlxtended.log_exception(self)

        channel.reply("Successfully unloaded all plug-ins except {}."
            .format(self.__class__.__name__))

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
                        channel.reply("Plug-in ^6{} ^7has failed to unload: {} - {}"
                            .format(plugin, e.__class__.__name__, e))
                        minqlxtended.log_exception(self)

            channel.reply("Successfully reloaded all plug-ins except {}."
                .format(self.__class__.__name__))

        f()
