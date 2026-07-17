# stats.py - a plugin for minqlxtended which provides statistics per-round on player gameplay
import minqlxtended

class stats(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("round_end", self.handle_round_end)
        self.add_hook("new_game", self.handle_new_game)
        
        self.old_seconds = 0
        self.old_damage = {}


    def handle_round_end(self, data):
        @minqlxtended.thread
        def f(self, data):
            time_elapsed = self.getElapsedSeconds(int(data["TIME"]))
            round_number = int(data["ROUND"])

            try:
                best_player, best_damage = self.getPlayerWithHighestDamage(round_number)
            except minqlxtended.NonexistentPlayerError:
                best_player, best_damage = None, 0

            if best_player is not None and best_player.valid:
                colour = "^1" if best_player.team == "red" else "^4"
                self.msg(f"^3DMG: ^5Round #{round_number}: {time_elapsed} secs.^7 {colour}{best_player.clean_name}^5 leads with {best_damage} damage dealt this round.")
            else:
                self.msg(f"^3DMG: ^5Round #{round_number}: {time_elapsed} secs.^7 ^3No damage leader recorded this round.")
        f(self, data)

    def handle_new_game(self, *args, **kwargs):
        self.old_seconds = 0
        self.old_damage = {}

    def getElapsedSeconds(self, seconds):
        seconds_delta = (seconds - self.old_seconds)
        self.old_seconds = seconds
        return seconds_delta

    def getPlayerWithHighestDamage(self, round_number):
        teams = self.teams()
        players = (teams["red"] + teams["blue"])
        best_player = None
        best_damage = 0
        for player in players:
            # Key by steam_id, not the recyclable client slot, so deltas follow the
            # actual player across slot reuse between rounds.
            try:
                last_damage = self.old_damage[player.steam_id]
            except KeyError:
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
            self.old_damage[player.steam_id] = player.stats.damage_dealt

        return (best_player, best_damage)
