# tp_vo.py - a plugin for minqlxtended to play custom The Purgery voiceovers in-game.

# Updated 31/07/2024 to make compatible with minqlxtended.

GAMEMODS        = ["infected", "quadhog"]
AUDIOPATH       = "tp_vo/"
AUDIOTABLEFILE  = "tp_vodb.json"
NAMESPERLINE    = 6

import minqlxtended
import re
import os
from time import time, sleep
from json import load
from random import randint
from collections import OrderedDict

TP_VO_WORKSHOP_ID = 572495786

class tp_vo(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("map", self.handle_map_load)
        self.add_hook("game_countdown", self.handle_game_countdown)
        self.add_hook("game_end", self.handle_game_end)
        self.add_hook("player_loaded", self.handle_player_loaded)
        self.add_hook("player_connect", self.handle_player_connect)
        self.add_hook("chat", self.handle_chat)
        
        self.add_command(("vonames", "listnames", "nameslist"), self.cmd_listnames)

        self.set_cvar_once("qlx_tpvoDebug", "0")
        self.set_cvar_once("qlx_tpvoRickroll", "0")
        # Own this default so play_sound() doesn't crash on int(None) when fun.py isn't loaded.
        self.set_cvar_once("qlx_funSoundDelay", "3")
        
        self.plugin_version = "2.0"

        self.last_sound = None

        self.vo_table = OrderedDict(dict())
        self._vo_patterns = []

        self._cache_variables()
        self.load_voiceovers()


    def _cache_variables(self):
        """ we do this to prevent lots of unnecessary engine calls """
        self._qlx_tpvoDebug = self.get_cvar("qlx_tpvoDebug", bool)
        self._qlx_tpvoRickroll = self.get_cvar("qlx_tpvoRickroll", bool)

    def load_voiceovers(self):
        self.audiotablefile = (os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/" + AUDIOTABLEFILE)
        self.debug_msg("^1TP_VO Debug:^7 __init__(): json data file: " + self.audiotablefile)
        if os.path.isfile(self.audiotablefile):
            with open(self.audiotablefile) as file:
                self.debug_msg("^1TP_VO Debug:^7 __init__(): loading in json voice-over data file")
                self.vo_table = OrderedDict(sorted(load(file).items()))
                self.debug_msg(f"^1TP_VO Debug:^7 __init__(): loaded {len(self.vo_table)} entries into the voice-over table")
        else:
            self.msg(f"^3Warning:^7 File ^1{self.audiotablefile}^7 not found.")
        self._compile_patterns()

    def _compile_patterns(self):
        """ Pre-compile each table key into a word-boundary regex so a key only
            fires as a whole word ('tc' no longer matches 'watch'). Sorted longest
            key first so the most specific phrase wins, since handle_chat() breaks
            on the first match (e.g. 'nice shot' beats 'shot'). """
        self._vo_patterns = [
            (pattern, re.compile(r"\b" + re.escape(pattern) + r"\b", flags=re.IGNORECASE), path)
            for pattern, path in sorted(self.vo_table.items(), key=lambda kv: len(kv[0]), reverse=True)
        ]

    def debug_msg(self, msg):
        if self._qlx_tpvoDebug:
            self.msg(msg)

    def cmd_listnames(self, player, msg, channel):
        """ Lists all the currently loaded voice-over recorded names for the calling player. """
        channel.reply(f"List of names sent to ^7{player.name}^7.")
        player.tell("Voice-over names list:")
        counter, line = 0, ""
        for pattern, path in self.vo_table.items():
            if counter >= NAMESPERLINE:
                player.tell(f"    ^3{line}")
                counter, line = 0, ""
            line += f"{pattern}  "
            counter += 1
        # Flush the final partial line; otherwise the last 1-6 names are dropped.
        if line:
            player.tell(f"    ^3{line}")
        player.tell(f"Total names: ^4{len(self.vo_table)}\n")
                
    def handle_map_load(self, *args, **kwargs):
        if TP_VO_WORKSHOP_ID not in self.game.workshop_items:
            self.game.workshop_items += [TP_VO_WORKSHOP_ID]

    @minqlxtended.thread
    def announceGametype(self):
        sleep(1.6)
        done = False
        for mod in GAMEMODS:
            if mod.lower() in self.game.factory.lower() and not done:
                self.debug_msg(f"^1TP_VO Debug:^7 announce_gametype(): playing mod announcement. mod: {mod.lower()}")
                super().play_sound(f"tp_vo/gametypes/mods/{mod.lower()}.ogg")
                done = True
        if not done:
            self.debug_msg(f"^1TP_VO Debug:^7 announce_gametype(): playing gametype announcement. gametype code: {self.game.type_short}")
            super().play_sound(f"tp_vo/gametypes/{self.game.type_short}.ogg")
                
    @minqlxtended.delay(2)
    def handle_game_countdown(self, *args, **kwargs):
        air_control = self.get_cvar("pmove_aircontrol", int)
        self.debug_msg(f"^1TP_VO Debug:^7 handle_game_countdown(): playing gamemode announcement. pmove_aircontrol == {air_control}")
        super().play_sound("tp_vo/rulesets/pql.ogg") if air_control else super().play_sound("tp_vo/rulesets/vql.ogg")
        self.announceGametype()
        
    @minqlxtended.delay(2)
    def handle_game_end(self, *args, **kwargs):
        if self._qlx_tpvoRickroll:
            rand = randint(0, 19)
        else:
            rand = True
        rand2 = randint(0, 9)
        if rand:
            if rand2:
                self.debug_msg("^1TP_VO Debug:^7 handle_game_end(): playing standard signoff")
                super().play_sound("tp_vo/general/great_game.ogg")
            else:
                self.debug_msg("^1TP_VO Debug:^7 handle_game_end(): playing alternate signoff")
                super().play_sound("tp_vo/general/good_game.ogg")
        else:
            self.debug_msg("^1TP_VO Debug:^7 handle_game_end(): rick-rolling")
            super().play_sound("tp_vo/samples/rickroll.ogg")
        
    @minqlxtended.delay(3)
    def handle_player_loaded(self, player):
        self.debug_msg("^1TP_VO Debug:^7 handle_player_loaded(): player loaded, playing welcome fanfare...")
        super().play_sound("tp_vo/purgery/welcome_to_the_purgery.ogg", player)

    def handle_player_connect(self, player):
        if player.steam_id == minqlxtended.owner():
            self.debug_msg("^1TP_VO Debug:^7 handle_player_connect(): purger connected, playing sound...")
            super().play_sound("tp_vo/players/purger.ogg")
            
    def play_sound(self, path):
        if not self.last_sound:
            pass
        elif int(time()) - self.last_sound < self.get_cvar("qlx_funSoundDelay", int):
            self.debug_msg("^1TP_VO Debug:^7 play_sound() stopped: delay is in effect")
            return
        self.debug_msg(f"^1TP_VO Debug:^7 play_sound(): old self.last_sound == {self.last_sound}")
        self.last_sound = int(time())
        self.debug_msg(f"^1TP_VO Debug:^7 play_sound(): new self.last_sound == {self.last_sound}")
        self.debug_msg(f"^1TP_VO Debug:^7 play_sound(): playing file {path}")
        # Batch-read the sounds_enabled flag in a single round-trip instead of one per player.
        players = self.players()
        keys = [f"minqlx:players:{p.steam_id}:flags:essentials:sounds_enabled" for p in players]
        values = self.db.mget(keys) if keys else []
        for p, v in zip(players, values):
            if v is None or bool(int(v)):
                super().play_sound(path, p)
            else:
                self.debug_msg(f"^1TP_VO Debug:^7 play_sound(): not playing for {p.clean_name} due to mute flag set")
                        
    def handle_chat(self, player, msg, channel):
        if channel != "chat": return

        text = self.clean_text(msg.lower())
        for pattern, regex, path in self._vo_patterns:
            if regex.search(text):
                self.debug_msg(f"^1TP_VO Debug:^7 handle_chat(): matched chat ^2{text}^7 with pattern ^2{pattern}^7")
                self.debug_msg(f"^1TP_VO Debug:^7 handle_chat(): calling self.play_sound({AUDIOPATH}{path})")
                self.play_sound(AUDIOPATH + path)
                break   
        
    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4tp_vo.py^7 - version {self.plugin_version}, created by Thomas Jones on 11/12/2015.")
