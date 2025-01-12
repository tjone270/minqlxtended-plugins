# Created by Thomas Jones on 19/09/2016 - thomas@tomtecsolutions.com
# votecommands.py - a minqlxtended plugin to add new /pass and /veto client commands for moderators.

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

class votecommands(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("client_command", self.handle_client_command)

        self.add_command(("yes", "no", "pass", "veto"), self.cmd_force_vote, 3, priority=minqlxtended.PRI_HIGHEST)
        self.plugin_version = "1.4"

        self._qlx_commandPrefix = self.get_cvar("qlx_commandPrefix")

    def handle_client_command(self, player, command):
        command = command.lower().split()[0]
        if command in ["pass", "veto", "yes", "no"]:
            self.do_vote(player, (True if command in ["pass", "yes"] else False))
            return minqlxtended.RET_STOP_ALL

    def cmd_force_vote(self, player, msg, channel):
        """ Forces the current vote. """
        command = msg[0].lower().replace(self._qlx_commandPrefix, "")
        
        action = False
        if command in ("yes", "pass"):
            action = True            

        self.do_vote(player, action)
        return minqlxtended.RET_STOP_ALL

    def do_vote(self, player, action):
        if not self.is_vote_active():
            player.tell(f"There is no current vote to ^6{'pass' if action else 'veto'}^7.")
            return minqlxtended.RET_STOP_ALL

        if not self.db.has_permission(player.steam_id, 3):
            player.tell(f"You don't have permission to ^6{action}^7 a vote.")
            return minqlxtended.RET_STOP_ALL

        if action:
            minqlxtended.force_vote(True)
            word = "^2passed"
        else:
            minqlxtended.force_vote(False)
            word = "^1vetoed"

        self.msg(f"{player.name}^7 {word}^7 the vote.")
       
    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4votecommands.py^7 - version {self.plugin_version}, created by Thomas Jones on 19/09/2016.")
