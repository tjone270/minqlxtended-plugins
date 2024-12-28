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
        self.add_command("define", self.cmd_define_term, usage="<term>")
        self.add_command("tomtec_versions", self.cmd_showversion)
        self.plugin_version = "1.5"
        
    @minqlxtended.thread
    def cmd_define_term(self, player, msg, channel):
        """ Provides the Urban Dictionary definition for the term provided. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            r = requests.get(DICT_API_URL.format(urllib.parse.quote(" ".join(msg[1:]))))
            r.raise_for_status()
            data = r.json()["list"][0]
            channel.reply("^4Definition^7: {}^7".format(shorten(self.strip_brackets(data["definition"]), width=150, placeholder="...")))
            if data["example"] != "":
                channel.reply("^4Example^7: {}^7".format(shorten(self.strip_brackets(data["example"]), width=250, placeholder="...")))
        except (TypeError, AttributeError):
            return minqlxtended.RET_USAGE
        except IndexError:
            channel.reply("^4Definition^7: ^1NO DEFINITIONS FOUND^7")
        except Exception as e:
            channel.reply("^1{}^7: {}".format(type(e).__name__, str(e)))
       
    def strip_brackets(self, string):
        return re.sub(r"\[|\]", "", string)

    def cmd_showversion(self, player, msg, channel):
        channel.reply("^4dictionary.py^7 - version {}, created by Thomas Jones on 22/08/16.".format(self.plugin_version))