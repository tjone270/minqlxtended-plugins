# minqlxtended-plugins
This is a collection of plugins for [minqlx](https://github.com/tjone270/minqlxtended).
The Python dependencies are included in requirements.txt. Make sure you run `python3 -m pip install -r requirements.txt` first.

This repository contains original plugins from the [minqlx-plugins](https://github.com/MinoMino/minqlx-plugins) repository which have been improved or further documented.

## CVAR Reference
This is a list of plugins and their CVARs. Set the CVARs by passing them as a command line argument or using `server.cfg`
like you would with any other QLDS CVAR.

- **plugin_manager**: Adds commands to load, reload and unload plugins at run-time.
- **essentials**: Adds commands for the regular QLDS commands and some more. Adds functionality to restrict teamsize voting and to pass votes before it fails if the majority votes yes.
  - `qlx_votepass`: A boolean deciding whether or not it should automatically pass votes before they fail if the majority voted yes.
    - Default: `1`
  - `qlx_votepassThreshold`: If `qlx_votepass` is `1`, determines the percentage (in decimal) of in-game players required to vote before it automatically passes any votes.
    - Default: `0.33`
  - `qlx_teamsizeMinimum`: The minimum teamsize allowed to vote for. `!teamsize` can override this.
    - Default: `1`
  - `qlx_teamsizeMaximum`: The maximum teamsize allowed to vote for. `!teamsize` can override this.
    - Default: `8` (if teams are full and teamsize is above 8, players will not be visible on the scoreboard)
- **ban**: Adds command to ban people for a set amount of time. Also adds functionality to ban for automatically for leaving too many games.
  - `qlx_leaverBan`: A boolean deciding whether or not it should automatically ban players for leaving.
    - Default: `0`
  - `qlx_leaverBanThreshold`:  If `qlx_leaverBan` is `1`, determines the percentage of games (in decimal) a player has
  to go below before automatic banning takes place.
    - Default: `0.63`
  - `qlx_leaverBanWarnThreshold`: If `qlx_leaverBan` is `1`, determines the percentage of games (in decimal) a player has
  to go below before a player is warned about his/her leaves.
    - Default: `0.78`
  - `qlx_leaverBanMinimumGames`: If `qlx_leaverBan` is `1`, determines the minimum number of games a player has to player before automatic banning takes place. If it determines a player cannot possibly recover even if they were to not leave any future games before the minimum, the player will  still be banned.
    - Default: `15`
- **balance**: Adds commands and CVARs to help balance teams in team games using ratings provided by third-party services (like [QLStats](https://qlstats.net)). 
  - `qlx_balanceAuto`: A boolean determining whether or not we should automatically try to balance teams if a shuffle vote passes.
    - Default: `1`
  - `qlx_balanceUseLocal`: A boolean determining whether or not it should use local ratings set by the `!setrating` command.
    - Default: `1`
  - `qlx_balanceMinimumSuggestionDiff`: The minimum rating difference before it suggests a switch when `!teams` is executed.
    - Default: `25`
  - `qlx_balanceUrl`: The address to the site hosting an instance of [PredatH0r's XonStat fork](https://github.com/PredatH0r/XonStat), which is currently the only supported rating service.
    - Default: `qlstats.net:8080`, which is hosted by PredatH0r himself.
  - `qlx_balanceApi`: The endpoint to use for ratings calls.
    - Default: `elo`
    - Alternative: `elo_b`
- **silence**: Adds commands to mute a player for an extended period of time. This persists across player reconnections, as opposed to the default mute behavior of `qzeroded`.
- **clan**: Adds commands to let players have persistent clan tags without having to change the name on Steam.
- **motd**: Adds commands to set a message of the day.
  - `qlx_motdSound`: The path to a sounds that is played when players connect and have the MOTD printed to them.
    - Default: `sound/vo/crash_new/37b_07_alt.wav`
  - `qlx_motdHeader`: The header printed right before the MOTD itself.
    - Default: `^6======= ^7Message of the Day ^6=======`
- **permission**: Adds commands to set player permissions.
- **names**: Adds a command to change names without relying on Steam.
  - `qlx_enforceSteamName`: A boolean deciding whether or not it should force players to use Steam names,
    but allowing colors, or to allow the player to set any name.
    - Default: `1`
- **raw**: Adds commands to interact with the Python interpreter directly. Useful for debugging.
- **log**: A plugin that logs chat and commands. All logs go to `fs_homepath/chatlogs`.
  - `qlx_chatlogs`: The maximum number of logs to keep around. If set to `0`, no maximum is enforced.
    - Default: `0`
  - `qlx_chatlogsSize`: The maximum size of a log in bytes before it starts with a new one.
    - Default: `5000000` (5 MB)
- **solorace**: A plugin that starts the game and keeps it running on a race server without requiring a minimum of two players, like you usually do with race.
- **docs**: A plugin that generates a command list of all the plugins currently loaded, in the form of a Markdown file.
- **workshop**: A plugin that allows the use of custom workshop items that the server might not reference by default, and thus not have the client download them automatically.
  - `qlx_workshopReferences`: A comma-separated list of workshop IDs for items you want to force the client to download. Use this for custom resources; the referenced PK3's filesystem will be superimposed upon the `pak00.pk3` filesystem.