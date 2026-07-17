# dictionary.py - a plugin for minqlxtended to enable players to call up Urban Dictionary definitions in-game.

# Updated 31/07/2024 to make compatible with minqlxtended.

# api docs: https://github.com/zdict/zdict/wiki/Urban-dictionary-API-documentation
DICT_API_URL = "http://api.urbandictionary.com/v0/define?term={}"

import minqlxtended
import requests
import urllib.parse
import re
from textwrap import shorten

class dictionary(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_command("define", self.cmd_define_term, usage="<term>")
        self.plugin_version = "1.6"
        
    def cmd_define_term(self, player, msg, channel):
        """ Provides the Urban Dictionary definition for the term provided. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        # Validate on the main thread so RET_USAGE works, then do the slow HTTP
        # request off-thread. (@thread on the command handler discards the return.)
        self._define_term(player, msg, channel)

    @minqlxtended.thread
    def _define_term(self, player, msg, channel):
        try:
            r = requests.get(DICT_API_URL.format(urllib.parse.quote(" ".join(msg[1:]))), timeout=5)
            r.raise_for_status()
            data = r.json()["list"][0]
            channel.reply(f"^6Definition^7: {shorten(self.strip_brackets(data['definition']), width=150, placeholder='...')}^7")
            if data["example"] != "":
                channel.reply(f"^6Example^7: {shorten(self.strip_brackets(data['example']), width=250, placeholder='...')}^7")
        except (TypeError, AttributeError, IndexError):
            channel.reply("^6Definition^7: ^3no definitions found^7")
        except Exception as e:
            channel.reply(f"^1{type(e).__name__}^7: {e}")
       
    def strip_brackets(self, string):
        return re.sub(r"\[|\]", "", string)

    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^6dictionary.py^7 - version {self.plugin_version}, created by Thomas Jones on 22/08/16.")