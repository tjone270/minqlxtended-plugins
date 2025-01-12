# Created by Thomas Jones on 01/01/2016 - thomas@tomtecsolutions.com
# votestats.py - a minqlxtended plugin to show who votes yes or no in-game/vote results.

# Updated 31/07/2024 to make compatible with minqlxtended.

# If you want to re-privatise votes, set the following cvar to 1: qlx_privatiseVotes

import minqlxtended

class votestats(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("vote", self.process_vote, priority=minqlxtended.PRI_LOWEST)
        self.add_hook("vote_ended", self.handle_vote_ended, priority=minqlxtended.PRI_LOWEST)

        self.add_command("votes", self.cmd_votes)

        self.set_cvar_once("qlx_privatiseVotes", "0")
        self._qlx_privatiseVotes = self.get_cvar("qlx_privatiseVotes", bool)

        self.plugin_version = "1.8"

        self.has_voted = []


    def cmd_votes(self, player, msg, channel):
        """ Prevents 'x voted y' messages from appearing for the calling player. Use again to re-enable these messages. """
        flag = self.db.get_flag(player, "votestats:votes_enabled", default=True)
        self.db.set_flag(player, "votestats:votes_enabled", not flag)
        if flag:
            word = "disabled"
        else:
            word = "enabled"
        player.tell("Player votes have been ^4{}^7.".format(word))
        return minqlxtended.RET_STOP_ALL
    
    def process_vote(self, player, yes):
        if self._qlx_privatiseVotes:
            return

        if player in self.has_voted:
            return
        
        if yes:
            word = "^2yes"
        else:
            word = "^1no"

        for p in self.players():
            if self.db.get_flag(p, "votestats:votes_enabled", default=True):
                p.tell("{}^7 voted {}^7.".format(player.name, word))
                
        self.has_voted.append(player)

    def handle_vote_ended(self, votes, vote, args, passed):
        self.has_voted = []
        self.msg(f"Vote results: ^2{votes[0]}^7 - ^1{votes[1]}^7.")
        
        if passed:
            if vote.lower().strip() == "map":
                changingToMapAndMode = args.lower().split()
                if len(changingToMapAndMode) > 1:
                    theMsg = f"The map is changing to ^6{changingToMapAndMode[0]}^7, with new factory ^6{changingToMapAndMode[1]}^7."
                else:
                    theMsg = f"The map is changing to ^6{changingToMapAndMode[0]}^7."

                self.msg(theMsg)
    
    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4votestats.py^7 - version {self.plugin_version}, created by Thomas Jones on 01/01/2016.")
