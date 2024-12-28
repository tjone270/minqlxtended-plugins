# stats.py - a plugin for minqlxtended which provides statistics per-round on player gameplay
import minqlxtended

class stats(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("round_end", self.handle_round_end)
        self.add_hook("new_game", self.handle_new_game)
        
        self.old_seconds = 0
        self.old_damage = {}


    @minqlxtended.next_frame
    def handle_round_end(self, data):
        time_elapsed = self.getElapsedSeconds(int(data["TIME"]))
        round_number = int(data["ROUND"])

        best_player_name = "(disconnected)"
        colour           = "^3"
        best_damage      = "^3(unknown)^7"
        
        try:
            best_player, best_damage = self.getPlayerWithHighestDamage(round_number)
            if best_player.valid:
                best_player_name = best_player.clean_name
                colour = "^1" if best_player.team == "red" else "^4"
        except:
            pass
            
        self.msg("^3DMG: ^5Round #{}: {} secs.^7 {}{}^5 leads with {} damage dealt this round.".format(round_number,
                                                                                                       time_elapsed,
                                                                                                       colour,
                                                                                                       best_player_name,
                                                                                                       best_damage))


    def handle_new_game(self, *args, **kwargs):
        self.old_seconds = 0
        self.old_damage = {}

    def getElapsedSeconds(self, seconds):
        seconds_delta = (seconds - self.old_seconds)
        self.old_seconds = seconds
        return seconds_delta

    def getPlayerWithHighestDamage(self, round_number):
        players = (self.teams()["red"] + self.teams()["blue"])
        best_player = {}
        best_damage = 0
        for player in players:
            try:
                last_damage = self.old_damage[player.id]
            except:
                last_damage = player.stats.damage_dealt
            if round_number != 1:
                delta = (player.stats.damage_dealt - last_damage)
                if (player.stats.damage_dealt > last_damage):
                    if (delta > best_damage):
                        best_player = player
                        best_damage = delta
            else:
                if (player.stats.damage_dealt > best_damage):
                    best_player = player
                    best_damage = player.stats.damage_dealt

        self.old_damage = {}
        for player in players:
            self.old_damage[player.id] = player.stats.damage_dealt

        return (best_player, best_damage)
