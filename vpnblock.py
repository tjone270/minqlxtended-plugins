import minqlxtended
import requests
import ipaddress

# VPN_IP_BLOCKS_URL = "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/vpn/ipv4.txt" # VPN IPs
VPN_IP_BLOCKS_URL = "https://raw.githubusercontent.com/X4BNet/lists_vpn/main/output/datacenter/ipv4.txt"  # Datacentre IPs

FLAG_NAME = "bypass_vpn_blocking"


class vpnblock(minqlxtended.Plugin):
    def __init__(self):
        super().__init__()
        self.add_hook("map", self.handle_map_load)
        self.add_hook("player_connect", self.handle_player_connect)

        self.add_command("vpn", self.cmd_vpn, 1, client_cmd_perm=1, usage="<id>")
        self.add_command("bypassvpn", self.cmd_bypassvpn, 4, client_cmd_perm=4, usage="<id>")

        self.set_cvar_once("qlx_blockVpnConnections", "1")

        self._vpn_buckets = {}        # first octet -> list of IPv4Network (prefix >= /8)
        self._vpn_wide = []           # networks broader than /8, or non-IPv4
        self._vpn_count = 0
        self._vpn_networks_loaded = False
        self._announced_blocked_players = set()
        self._update_cache()

    def _find_vpn_network(self, ip):
        """Return the matching VPN network for *ip*, or None. Only scans the
        networks sharing the address's leading octet (plus the few broad ones)."""
        try:
            address = ipaddress.ip_address(ip)
        except ValueError:
            return None
        for network in self._vpn_wide:
            if address in network:
                return network
        if isinstance(address, ipaddress.IPv4Address):
            for network in self._vpn_buckets.get(int(address) >> 24, ()):
                if address in network:
                    return network
        return None

    def _warn_if_unenforced(self):
        if self.get_cvar("qlx_blockVpnConnections", bool) and not self._vpn_networks_loaded:
            self.msg("vpnblock: ^1WARNING^7: VPN blocking is enabled but no network list is "
                     "loaded, so VPN connections are currently being allowed.")

    def handle_map_load(self, *args, **kwargs):
        self._update_cache()

    def handle_player_connect(self, player):
        if (self.get_cvar("qlx_blockVpnConnections", bool)) and (self._vpn_count) and (not player.is_bot):
            if self.db.get_flag(player, FLAG_NAME):
                return  # bypass VPN blocking for this player

            vpn_network = self._find_vpn_network(player.ip)
            if vpn_network is not None:
                if player.steam_id not in self._announced_blocked_players:
                    self.msg(f"vpnblock: Denied connection from {player.name}^7 as they are using a VPN.")
                    self._announced_blocked_players.add(player.steam_id)
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

        is_vpn = self._find_vpn_network(target_player.ip) is not None

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
        try:
            req = requests.get(url=VPN_IP_BLOCKS_URL, timeout=10)
        except requests.RequestException as e:
            self.msg(f"vpnblock: ^1Error^7 fetching the latest VPN network blocks: {e}")
            self._warn_if_unenforced()
            return
        if not req.ok:
            self.msg(f"vpnblock: Got ^1{req.status_code} ({req.reason})^7 when fetching the latest VPN network blocks.")
            self._warn_if_unenforced()
            return

        buckets = {}
        wide = []
        parsed = 0
        skipped = 0
        for token in req.text.split():
            try:
                network = ipaddress.ip_network(token.strip(), strict=False)
            except ValueError:
                # One malformed line (or an HTML error body) must not discard the
                # whole update; skip and count it instead.
                skipped += 1
                continue
            parsed += 1
            if isinstance(network, ipaddress.IPv4Network) and network.prefixlen >= 8:
                buckets.setdefault(int(network.network_address) >> 24, []).append(network)
            else:
                wide.append(network)

        if not parsed:
            self.msg("vpnblock: ^1No usable VPN network blocks parsed^7; keeping the previous list.")
            self._warn_if_unenforced()
            return

        self._vpn_buckets = buckets
        self._vpn_wide = wide
        self._vpn_count = parsed
        self._vpn_networks_loaded = True
        note = f" (^1{skipped:,}^7 malformed lines skipped)" if skipped else ""
        self.msg(f"vpnblock: Found ^6{parsed:,}^7 VPN network blocks to deny connections from.{note}")
