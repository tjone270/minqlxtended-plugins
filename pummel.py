# pummel.py - a plugin for minqlxtended to track and report on player pummels.
# Copyright (C) 2016 mattiZed (github) aka mattiZed (ql)

# You can redistribute it and/or modify it under the terms of the 
# GNU General Public License as published by the Free Software Foundation, 
# either version 3 of the License, or (at your option) any later version.

# You should have received a copy of the GNU General Public License
# along with this plugin. If not, see <http://www.gnu.org/licenses/>.

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

# DB related
PLAYER_KEY = "minqlx:players:{}"

class pummel(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("kill", self.handle_kill)
        
        self.add_command("pummel", self.cmd_pummel)
    

    def handle_kill(self, victim, killer, data):
        if data["MOD"] == "GAUNTLET" and self.game.state == "in_progress":
            if (killer.is_bot or victim.is_bot):
                return # ignore bot related action.
            
            self.play_sound("sound/vo_evil/humiliation1")

            @minqlxtended.thread
            def f(self, victim, killer):
                self.db.sadd(f"{PLAYER_KEY.format(killer.steam_id)}:pummeled", str(victim.steam_id))
                self.db.incr(f"{PLAYER_KEY.format(killer.steam_id)}:pummeled:{str(victim.steam_id)}")
        
                killer_score = self.db[f"{PLAYER_KEY.format(killer.steam_id)}:pummeled:{str(victim.steam_id)}"]
                victim_score = 0
                if PLAYER_KEY.format(victim.steam_id) + ":pummeled:" + str(killer.steam_id) in self.db:
                    victim_score = self.db[f"{PLAYER_KEY.format(victim.steam_id)}:pummeled:{str(killer.steam_id)}"]
                
                self.msg(f"^1PUMMEL!^7 {killer.name} ^1{killer_score}^7:^1{victim_score}^7 {victim.name}")
            f(self, victim, killer)
    
    def cmd_pummel(self, player, msg, channel):
        """ Shows the calling player all the players they've pummeled who are currently connected to this server. """
        pummels = self.db.smembers(f"{PLAYER_KEY.format(player.steam_id)}:pummeled")
        players = self.teams()["spectator"] + self.teams()["red"] + self.teams()["blue"] + self.teams()["free"]
        
        msg = ""
        for p in pummels:
            for pl in players:
                if p == str(pl.steam_id):
                    count = self.db[f"{PLAYER_KEY.format(player.steam_id)}:pummeled:{p}"]
                    msg += pl.name + ": ^1" + count + "^7 "
        
        if msg == "":
            self.msg(f"{player}^7 has not pummeled anybody on this server.")
        else:
            self.msg(f"Pummel stats for {player}^7:")
            self.msg(msg)