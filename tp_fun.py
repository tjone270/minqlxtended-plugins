# tp_fun.py - a plugin for minqlxtended containing community fun.

# Updated 31/07/2024 to make compatible with minqlxtended.

import minqlxtended
from random import randint

class tp_fun(minqlxtended.Plugin):
    def __init__(self):
        self.add_command(("msg", "message"), self.cmd_screenmessage, 1, usage="[id] <text>") # Merozollo requested
        self.add_command("smile", self.cmd_elated_emoji) # Purger requested
        self.add_command("pentagram", self.cmd_pentagram, 1, usage="<id>") # Merozollo requested
        self.add_command("tomtec_versions", self.cmd_showversion)
        self.add_command("purger", self.cmd_purger)
        self.add_command(("vaginadepth", "vaginaldepth", "vagdep"), self.cmd_vagdep)
        self.add_command(("penislength", "penlen"), self.cmd_penlen)
        self.add_command(("peniswidth", "penwidth", "penwid"), self.cmd_penwidth)
        self.add_command(("cupsize", "boobsize"), self.cmd_boobsize)
        self.add_command("fuckyou", self.cmd_printfu, 5)
        self.add_command("drawline", self.cmd_drawline, 5, usage="<start plane> <from> <to> <step> <z start>")
        self.add_command("bury", self.cmd_bury, 3, usage="<id>")
        self.add_command("specplay", self.cmd_spec_play, 5)
        self.add_command("digup", self.cmd_digup, 3, usage="<id>")

        self.plugin_version = "2.0"

    def cmd_spec_play(self, player, msg, channel):
        if len(msg) > 1:
            z_pos_boost = int(msg[1])
        else:
            z_pos_boost = 0
    
        origin = player.position()
    
        for p in self.teams()["spectator"]:
            if p.id == player.id:
                continue # don't do it to the caller
            z_pos_boost += 100
            p.is_alive = True
            p.velocity(x=randint(100, 400), y=randint(100, 400), z=0)
            p.position(x=origin[0], y=origin[1], z=(origin[2] + z_pos_boost))
            p.weapons(reset=True, hands=True)
            p.ammo(reset=True)
            @minqlxtended.next_frame
            def next_frame(p):
                p.weapon = 15
            next_frame(p)
            player.tell("{}^7 is spawned {} units above you.".format(p, z_pos_boost))

    def cmd_bury(self, player, msg, channel):
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            target_player = self.player(int(msg[1]))
        except minqlxtended.NonexistentPlayerException:
            return minqlxtended.RET_USAGE

        if self.game.state == "in_progress":
            player.tell("This command can be used during warm-up only.")
            return minqlxtended.RET_STOP_ALL

        target_player.position(z=target_player.position()[2] - 25)

    def cmd_digup(self, player, msg, channel):
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        try:
            target_player = self.player(int(msg[1]))
        except minqlxtended.NonexistentPlayerException:
            return minqlxtended.RET_USAGE

        if self.game.state == "in_progress":
            player.tell("This command can be used during warm-up only.")
            return minqlxtended.RET_STOP_ALL

        target_player.position(z=target_player.position()[2] + 25)

    def cmd_drawline(self, player, msg, channel):
        if len(msg) < 6:
            return minqlxtended.RET_USAGE

        #MAX_DISTANCE = 1024
        
        def dropflag(x, y, z):
            minqlxtended.spawn_item(36, int(x), int(y), int(z))
            
        drawPlaneStart  = str(msg[1]).lower().split("=")
        drawFrom        = int(msg[2])
        drawTo          = int(msg[3])
        drawStep        = int(msg[4])
        drawZAxis       = int(msg[5])

        #if (abs(drawFrom - drawTo) >= MAX_DISTANCE):
        #    channel.reply("Distance too long. (>= {})".format(MAX_DISTANCE))
        if (drawPlaneStart[0] == "x"):
            for step in range(drawFrom, drawTo, drawStep):
                dropflag(int(drawPlaneStart[1]), int(step), int(drawZAxis))
        elif (drawPlaneStart[0] == "y"):
            for step in range(drawFrom, drawTo, drawStep):
                dropflag(int(step), int(drawPlaneStart[1]), int(drawZAxis))
        else:
            channel.reply("Invalid info entered.")

               
    def cmd_purger(self, player, msg, channel):
        channel.reply("""
______                          
| ___ \                         
| |_/ /   _ _ __^4 __ _ ^7 ___ _ __ 
|  __/ | | | '__^4/ _` |^7/ _ \ '__|
| |  | |_| | | ^4| (_| |^7  __/ |   
\_|   \__,_|_|  ^4\__, |^7\___|_|   
                 ^4__/ |^7          
                ^4|___/^7           

    """)
        

    def talk_beep(self, player=None):
        if not player:
            self.play_sound("sound/player/talk.ogg")
        else:
            self.play_sound("sound/player/talk.ogg", player)
            
    def cmd_elated_emoji(self, player, msg, channel):
        num1 = randint(0,6)
        num2 = randint(0,6)
        minqlxtended.client_command(player.id, "say ^{}:^{}D".format(num1, num2))
        return minqlxtended.RET_STOP_ALL
        
    def cmd_pentagram(self, player, msg, channel):
        if len(msg) < 2:
            return minqlxtended.RET_USAGE
        
        try:
            pentagramee = self.player(int(msg[1]))
        except:
            player.tell("Invalid ID.")
            return

        pentagramee.powerups(battlesuit=3)
        self.msg("{}^7 has got the ^1Pentagram of Protection^7!".format(pentagramee.name))
        
    def cmd_penlen(self, player, msg, channel):
        playerName = player.clean_name
        randNum = randint(0,11)
        if randNum == 0:
            channel.reply("^7{}^7's penis length: ^40 inches (inverted!)^7".format(player))
        else:
            channel.reply("^7{}^7's penis length: ^4{} inch{}^7".format(player, randNum, "es" if randNum != 1 else ""))

    def cmd_penwidth(self, player, msg, channel):
        randNum = randint(0, 4)
        if randNum == 0:
            channel.reply("^7{}^7's penis width: ^40 inches (anti-girth!)^7".format(player))
        elif randNum == 4:
            channel.reply("^7{}^7's penis width: ^44 inches (mega-girth!)^7".format(player))
        else:
            channel.reply("^7{}^7's penis width: ^4{} inch{}^7".format(player, randNum, "es" if randNum != 1 else ""))

    def cmd_vagdep(self, player, msg, channel):
        playerName = player.clean_name
        randNum = randint(0,11)
        if randNum == 0:
            channel.reply("^7{}^7's vaginal depth: ^40 inches (are you trans?)^7".format(player))
        else:
            channel.reply("^7{}^7's vaginal depth: ^4{} inch{}^7".format(player, randNum, "es" if randNum != 1 else ""))

    def cmd_boobsize(self, player, msg, channel):
        playerName = player.clean_name
        randNum = randint(0,5)
        if randNum == 0:
            cupSize = "A"
        elif randNum == 1:
            cupSize = "B"
        elif randNum == 2:
            cupSize = "C"
        elif randNum == 3:
            cupSize = "D"
        elif randNum == 4:
            cupSize = "DD"
        elif randNum == 5:
            cupSize = "Z (discount wheelbarrow at Bunnings!)"

        channel.reply("^7{}^7's cup size: ^4{}^7".format(playerName, cupSize))
           
    def cmd_screenmessage(self, player, msg, channel):
        if len(msg) < 2:
            return minqlxtended.RET_USAGE

        self.center_print(" ".join(msg[1:]))
        self.play_sound("sound/world/klaxon2.wav")

    def cmd_printfu(self, player, msg, channel):
        minqlxtended.send_server_command(None, "cp \"^0FUCK YOU\n^1FUCK YOU\n^2FUCK YOU\n^3FUCK YOU\n^4FUCK YOU\n^5FUCK YOU\n^6FUCK YOU\"\n")

    def cmd_showversion(self, player, msg, channel):
        channel.reply("^4tp_fun.py^7 - version {}, created by the community.".format(self.plugin_version))
