# Created by Thomas Jones on 19/09/2016 - thomas@tomtecsolutions.com
# votecommands.py - a minqlxtended plugin to add new /pass and /veto client commands for moderators.

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

class votecommands(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("client_command", self.handle_client_command)

        self.add_command("tomtec_versions", self.cmd_showversion)
        self.add_command(("yes", "no", "pass", "veto"), self.cmd_force_vote, 3, priority=minqlxtended.PRI_HIGHEST)
        self.plugin_version = "1.3"

    def handle_client_command(self, player, command):
        command = command.lower().split()[0]
        if command in ["pass", "veto", "yes", "no"]:
            self.do_vote(player, (True if command in ["pass", "yes"] else False))
            return minqlxtended.RET_STOP_ALL

    def cmd_force_vote(self, player, msg, channel):
        """ Forces the current vote. """
        command = msg[0].lower().replace(self.get_cvar("qlx_commandPrefix"), "")
        
        if command == "yes" or command == "pass":
            action = True
        elif command == "no" or command == "veto":
            action = False

        self.do_vote(player, action)
        return minqlxtended.RET_STOP_ALL

    def do_vote(self, player, action):
        if not self.is_vote_active():
            player.tell("There is no current vote to ^4{}^7.".format("pass" if action else "veto"))
            return minqlxtended.RET_STOP_ALL

        if not self.db.has_permission(player.steam_id, 3):
            player.tell("You don't have permission to ^4{}^7 a vote.".format(action))
            return minqlxtended.RET_STOP_ALL

        if action:
            minqlxtended.force_vote(True)
            word = "^2passed"
        else:
            minqlxtended.force_vote(False)
            word = "^1vetoed"

        self.msg("{}^7 {}^7 the vote.".format(player.name, word))
       
    def cmd_showversion(self, player, msg, channel):
        channel.reply("^4votecommands.py^7 - version {}, created by Thomas Jones on 19/09/2016.".format(self.plugin_version))
