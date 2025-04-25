# aliases.py - a plugin for minqlxtended to show player aliases

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended

class aliases(minqlxtended.Plugin):
    def __init__(self):
        self.add_command("alias", self.cmd_alias, usage="<id>")
        self.add_command("clearaliases", self.cmd_clearaliases, 5)

        self.set_cvar_once("qlx_aliasLimitOutputLines", "15")

        self.plugin_version = "2.1"

        self._linelimit = self.get_cvar("qlx_aliasLimitOutputLines", int)

    @minqlxtended.thread
    def cmd_alias(self, player, msg, channel):
        """Provides a list of aliases the server is aware of for the player ID/Steam ID provided."""
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            ident = int(msg[1])
            if 0 <= ident < 64:
                target_player = self.player(ident)
                if target_player.is_bot:
                    channel.reply("Bots do not have aliases!")
                    return
                steam_id = target_player.steam_id
                player_name = target_player.name
                player_iplist = list(self.db.smembers(f"minqlx:players:{steam_id}:ips"))
            else:
                steam_id = ident
                player_name = ident
                player_iplist = list(self.db.smembers(f"minqlx:players:{steam_id}:ips"))
        except ValueError:
            channel.reply("Invalid ID. Use either a client ID or a SteamID64.")
            return
        except minqlxtended.NonexistentPlayerError:
            channel.reply("Invalid client ID. Use either a client ID or a SteamID64.")
            return
        data = dict()
        steamids = list()

        for ip_address in player_iplist:
            steamids += list(self.db.smembers(f"minqlx:ips:{ip_address}"))

        steamids = self.dedupe(steamids)

        for steamid in steamids:
            data[steamid] = list(self.db.lrange(f"minqlx:players:{steamid}", 0, -1))

        for sid, names in data.items():
            if lineused == self._linelimit:
                break
            used_names = list()
            response += f" ^6•^7 {sid}:\n"
            for name in names:
                if name not in used_names:
                    if lineused == self._linelimit:
                        response += f"^1Remaining aliases truncated (line limit set to {self._linelimit})^7\n"
                        break
                    response += f"    ^6•^7 {self.clean_text(name)}\n"
                    lineused += 1
                    used_names.append(name)

        channel.reply(response)
    def cmd_clearaliases(self, player, msg, channel):
        """Clears all alias records from the server database."""
        if player.steamid != minqlxtended.owner():
            player.tell("You must be the owner of the server to execute this command.")
            return

        players = self.db.smembers("minqlx:players")
        for p in players:
            del self.db[f"minqlx:players:{p}"]
        channel.reply(f"All aliases for all players ({len(players)} players in total) were cleared.")

    def dedupe(self, lst):
        return list(dict.fromkeys(lst))

    def cmd_showversion(self, player, msg, channel):
        channel.reply(f"^4aliases.py^7 - version {self.plugin_version}, created by Thomas Jones on 14/12/2015.")
