# Created by Thomas Jones (tjone270) on 10/02/2025 - me@thomasjones.id.au
# glasshouse.py - a plugin for minqlxtended to discourage players from calling frivolous kick/ban votes on other players by kicking the caller if the vote fails.
import minqlxtended


class glasshouse(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("vote_started", self.handle_vote_started, priority=minqlxtended.PRI_LOWEST)
        self.add_hook("vote_ended", self.handle_vote_ended, priority=minqlxtended.PRI_LOWEST)

        self.affected_votes = ["kick", "clientkick", "tempban"]
        self.last_kickvote_caller = None  # steam_id of the caller, or None

    def handle_vote_started(self, caller, vote, args):
        vote = vote.lower().strip()
        # caller is None for engine/plugin-initiated votes; has_permission(None) raises.
        if caller and (vote in self.affected_votes) and (not self.db.has_permission(caller, 1)):
            self.last_kickvote_caller = caller.steam_id
            self.msg(f"^3If this vote fails, ^7{caller.name}^3 will be kicked instead.")

    def handle_vote_ended(self, votes, vote, args, passed):
        vote = vote.lower().strip()
        if (not passed) and (vote in self.affected_votes) and (self.last_kickvote_caller is not None):
            # Re-resolve the stored steam_id to a currently-connected player so we
            # don't kick whoever now occupies the caller's old client slot (the
            # caller may have disconnected during the ~30s vote).
            caller = self.player(self.last_kickvote_caller)
            if caller:
                caller.kick("was kicked for calling an unsuccessful kick/ban vote.")

        self.last_kickvote_caller = None
