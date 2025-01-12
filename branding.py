# branding.py - a plugin for minqlxtended to brand your server.

# Updated 31/07/2024 to make compatible with minqlxtended.

"""
Branding.py is a minqlx plugin that permits you to personalise your server with your own information.
Simply put the plugin in the 'minqlx-plugins' folder, !load the plugin, and set these cvars:

    qlx_serverBrandName                  - Where the map name usually appears, the text set in this cvar will appear instead.
    qlx_serverBrandTopField              - Where the map author credit (line 1) appears, the text set in this cvar will appear after the credit.
    qlx_serverBrandBottomField           - Where the map author credit (line 2) appears, the text set in this cvar will appear after the credit.

    qlx_connectMessage                   - When the player is at the awaiting challenge screen when they first connect to the server, text will appear here.
    qlx_loadedMessage                    - When the player gets to the menu after connecting, and clicks Join or Spectate, they'll get centre print from this cvar.
    qlx_countdownMessage                 - When the countdown begins, this text will appear mid-screen. (like the qlx_loadedMessage does)
    qlx_endOfGameMessage                 - When the game finishes, it'll put the text in this cvar in the text box on the left.
    
    qlx_brandingPrependMapName           - This cvar will put the map name before your qlx_serverBrandName.                     Default: 0
    qlx_brandingAppendGameType           - Will add the game type after your qlx_serverBrandName.                               Default: 0
    qlx_rainbowBrandName                 - Make the entire map name (qlx_serverBrandName) appear in rainbow colouring.          Default: 0
    
Once set, change maps, and you'll see the map loading screen is changed.
"""

import minqlxtended


CS_MESSAGE = 3
CS_AUTHOR = 678
CS_AUTHOR2 = 679

class branding(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("new_game", self.handle_map)
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("game_countdown", self.handle_game_countdown)
        self.add_hook("game_end", self.handle_game_end)
        
        self.set_cvar_once("qlx_brandingPrependMapName", "0")
        self.set_cvar_once("qlx_brandingAppendGameType", "0")
        self.set_cvar_once("qlx_rainbowBrandName", "0")
        
        self.plugin_version = "2.3"

        self.connected_players = []

        self._cache_variables()


    def _cache_variables(self):
        """ we do this to prevent lots of unnecessary engine calls """
        self._qlx_brandingPrependMapName = self.get_cvar("qlx_brandingPrependMapName", bool)
        self._qlx_serverBrandName = self.get_cvar("qlx_serverBrandName", str)
        self._qlx_brandingAppendGameType = self.get_cvar("qlx_brandingAppendGameType", bool)
        self._qlx_serverBrandTopField = self.get_cvar("qlx_serverBrandTopField", str)
        self._qlx_serverBrandBottomField = self.get_cvar("qlx_serverBrandBottomField", str)
        self._qlx_rainbowBrandName = self.get_cvar("qlx_rainbowBrandName", bool)
        self._qlx_connectMessage = self.get_cvar("qlx_connectMessage", str)
        self._qlx_loadedMessage = self.get_cvar("qlx_loadedMessage", str)
        self._qlx_countdownMessage = self.get_cvar("qlx_countdownMessage", str)
        self._qlx_endOfGameMessage = self.get_cvar("qlx_endOfGameMessage", str)

    def handle_map(self):
        self._cache_variables()

        message = minqlxtended.get_configstring(CS_MESSAGE)
        author = minqlxtended.get_configstring(CS_AUTHOR)
        author2 = minqlxtended.get_configstring(CS_AUTHOR2)

        if self._qlx_serverBrandName and self._qlx_brandingPrependMapName and self._qlx_brandingAppendGameType:
            message = f"{self.game.map_title} {self._qlx_serverBrandName} {self.game.type}"
        elif self._qlx_serverBrandName and self._qlx_brandingPrependMapName:
            message = f"{self.game.map_title} {self._qlx_serverBrandName}"
        elif self._qlx_serverBrandName and self._qlx_brandingAppendGameType:
            message = f"{self._qlx_serverBrandName} {self.game.type}"
        elif self._qlx_serverBrandName:
            message = self._qlx_serverBrandName

        if self._qlx_serverBrandTopField:
            author = f"{(self.game.map_subtitle1 + ' - ') if self.game.map_subtitle1 else ''}{self._qlx_serverBrandTopField}"

        if self._qlx_serverBrandBottomField:
            author2 = f"{(self.game.map_subtitle2 + ' - ') if self.game.map_subtitle2 else ''}{self._qlx_serverBrandBottomField}"

        if self._qlx_rainbowBrandName:
            # Thanks Mino for this bit!
            def rotating_colors():
                i = 0
                while True:
                    res = (i % 7) + 1
                    i += 1
                    yield res

            r = rotating_colors()
            res = ""
            for i in range(len(message)):
                res += f"^{next(r)}{message[i]}"

        minqlxtended.set_configstring(CS_MESSAGE, message)
        minqlxtended.set_configstring(CS_AUTHOR, author)
        minqlxtended.set_configstring(CS_AUTHOR2, author2)   

    def handle_player_connect(self, player):
        if (self._qlx_connectMessage) and (player not in self.connected_players):
            self.connected_players.append(player)
            return f"{self._qlx_connectMessage}\n^7This server is running ^4branding.py^7. ^2http://github.com/tjone270/Quake-Live^7.\n"
        
    def handle_player_loaded(self, player):
        if self._qlx_loadedMessage:
            self.center_print(self._qlx_loadedMessage, player.id)

        if (self._qlx_connectMessage) and (player in self.connected_players):
            self.connected_players.remove(player)

    def handle_game_countdown(self):
        if self._qlx_countdownMessage:
            self.center_print(self._qlx_countdownMessage)

    def handle_game_end(self, data):
        if self._qlx_endOfGameMessage:
            self.msg(self._qlx_endOfGameMessage)
            
    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4branding.py^7 - version {self.plugin_version}, created by Thomas Jones on 06/11/2015.")
