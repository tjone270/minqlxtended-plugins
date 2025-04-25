import minqlxtended
import requests
import ipaddress

# VPN_IP_BLOCKS_URL = "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/vpn/ipv4.txt" # VPN IPs
VPN_IP_BLOCKS_URL = "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/datacenter/ipv4.txt"  # Datacentre IPs

FLAG_NAME = "bypass_vpn_blocking"


class vpnblock(minqlxtended.Plugin):
    def __init__(self):
        self.add_hook("map", self.handle_map_load)
        self.add_hook("player_connect", self.handle_player_connect)

        self.add_command("vpn", self.cmd_vpn, 1, client_cmd_perm=1, usage="<id>")
        self.add_command("bypassvpn", self.cmd_bypassvpn, 4, client_cmd_perm=4, usage="<id>")

        self.set_cvar_once("qlx_blockVpnConnections", "1")

        self._vpn_networks = []
        self._update_cache()

    def handle_map_load(self, *args, **kwargs):
        self._update_cache()

    def handle_player_connect(self, player):
        if (self.get_cvar("qlx_blockVpnConnections", bool)) and (self._vpn_networks) and (not player.is_bot):
            if self.db.get_flag(player, FLAG_NAME):
                return  # bypass VPN blocking for this player

            player_address = ipaddress.ip_address(player.ip)
            for vpn_network in self._vpn_networks:
                if player_address in vpn_network:
                    self.msg(f"vpnblock: Denied connection from {player.name}^7 as they are using a VPN.")
                    return f"^7VPN connections aren't allowed on The Pur^4g^7ery. ^2Disable ^2your ^2VPN ^2to ^2join ^2the ^2match.\n^7Your IP exists within a known VPN range (^4{player.ip}^7 is in ^4{vpn_network.compressed}^7), if you feel there is a mistake please visit ^3thepurgery.com/discord^7.\n"

    def cmd_vpn(self, player, msg, channel):
        """Checks to see if the specified player is playing from a known VPN/datacentre-based IP."""
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            i = int(msg[1])
            target_player = self.player(i)
            if not (0 <= i < 64) or not target_player:
                raise ValueError
        except ValueError:
            player.tell("Invalid client ID.")
            return minqlxtended.RET_STOP_ALL
        except minqlxtended.NonexistentPlayerError:
            channel.reply("Invalid client ID.")
            return

        is_vpn = False
        target_player_address = ipaddress.ip_address(target_player.ip)
        for vpn_network in self._vpn_networks:
            if target_player_address in vpn_network:
                is_vpn = True
                break

        if is_vpn:
            player.tell(f"{target_player.name}^7's IP address ^2is^7 a known VPN/datacentre-based IP.")
        else:
            player.tell(f"{target_player.name}^7's IP address ^1is not^7 a known VPN/datacentre-based IP.")

        return minqlxtended.RET_STOP_ALL

    def cmd_bypassvpn(self, player, msg, channel):
        """Allows the specified player to connect to the server while using a VPN, bypassing any VPN blocking."""
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            ident = int(msg[1])
            target_player = None
            if 0 <= ident < 64:
                target_player = self.player(ident)
                ident = target_player.steam_id
        except ValueError:
            channel.reply("Invalid ID. Use either a client ID or a SteamID64.")
            return
        except minqlxtended.NonexistentPlayerError:
            channel.reply("Invalid client ID. Use either a client ID or a SteamID64.")
            return

        if target_player:
            name = target_player.name
        else:
            name = f"^6{ident}"

        flag = self.db.get_flag(ident, FLAG_NAME)
        self.db.set_flag(ident, FLAG_NAME, not flag)

        if not flag:
            channel.reply(f"{name}^7 is allowed to bypass the VPN blocker.")
        else:
            channel.reply(f"{name}^7 is now blocked from using VPNs.")

    @minqlxtended.thread
    def _update_cache(self):
        req = requests.get(url=VPN_IP_BLOCKS_URL)
        if req.ok:
            self._vpn_networks = [ipaddress.ip_network(cidr.strip()) for cidr in req.text.split()]
            self.msg(f"vpnblock: Found ^6{len(self._vpn_networks)}^7 VPN network blocks to deny connections from.")
        else:
            self.msg(f"vpnblock: Got ^1{req.status_code} ({req.reason})^7 when fetching the latest VPN network blocks.")
