# aliases.py - a plugin for minqlxtended to show player aliases

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

class aliases(minqlxtended.Plugin):
    def __init__(self):
        self.add_command("alias", self.cmd_alias, usage="<id>")
        self.add_command("clearaliases", self.cmd_clearaliases, 5)

        self.set_cvar_once("qlx_aliasLimitOutputLines", "15") 

        self.plugin_version = "2.0"

    @minqlxtended.thread
    def cmd_alias(self, player, msg, channel):
        """ Provides a list of aliases the server is aware of for the player ID/Steam ID provided. """
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            ident = int(msg[1])
            if 0 <= ident < 64:
                steam_id = self.player(ident).steam_id
                player_name = self.player(ident).name
                player_iplist = list(self.db.smembers("minqlx:players:{}:ips".format(steam_id)))
            else:
                steam_id = ident
                player_name = ident
            player_iplist = list(self.db.smembers("minqlx:players:{}:ips".format(steam_id)))
        except ValueError:
            channel.reply("Invalid ID. Use either a client ID or a SteamID64.")
            return
        except minqlxtended.NonexistentPlayerError:
            channel.reply("Invalid client ID. Use either a client ID or a SteamID64.")
            return
        
        data = dict()
        steamids = list()

        for ip_address in player_iplist:
            steamids += list(self.db.smembers("minqlx:ips:{}".format(ip_address)))
        
        steamids = self.dedupe(steamids)

        for steamid in steamids:
            data[steamid] = list(self.db.lrange("minqlx:players:{}".format(steamid), 0, -1))
        
        linelimit = self.get_cvar("qlx_aliasLimitOutputLines", int)
        lineused = 1
        response = "{}^7's aliases:\n".format(player_name)

        for sid, names in data.items():
            if lineused == linelimit:
                break
            used_names = list()
            response += " ^6•^7 {}:\n".format(sid)
            for name in names:
                if name not in used_names:
                    if lineused == linelimit:
                        response += "^1Remaining aliases truncated (line limit set to {})^7\n".format(linelimit)
                        break
                    response += "    ^6•^7 {}\n".format(self.clean_text(name))
                    lineused += 1
                    used_names.append(name)

        channel.reply(response)
        
    def cmd_clearaliases(self, player, msg, channel):
        """ Clears all alias records from the server database. """
        if player.steamid != minqlxtended.owner():
            player.tell("You must be the owner of the server to execute this command.")
            return

        players = self.db.smembers("minqlx:players")
        for p in players:
            del self.db["minqlx:players:{}".format(p)]
        channel.reply("All aliases for all players ({} players in total) were cleared.".format(len(players)))

    def dedupe(self, lst):
        return list(dict.fromkeys(lst))

    def cmd_showversion(self, player, msg, channel):
        channel.reply("^4aliases.py^7 - version {}, created by Thomas Jones on 14/12/2015.".format(self.plugin_version))
