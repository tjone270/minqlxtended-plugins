# minqlxtended - Extends Quake Live's dedicated server with extra functionality and scripting.
# Copyright (C) 2015 Mino <mino@minomino.org>
# Copyright (C) 2024-2026 Thomas Jones <me@thomasjones.id.au>

# This file is part of minqlxtended.

# minqlxtended is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# minqlxtended is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with minqlxtended. If not, see <http://www.gnu.org/licenses/>.

import minqlxtended
import os.path
from os import linesep
from datetime import datetime
from html import escape

FORMATS = {
    "markdown": "command_list.md",
    "twig": "command_list.twig",
    "jinja": "command_list.jinja",
}

TEMPLATE_FLAVOURS = {
    "twig": {"macros": "macros.tmpl", "badge": "permissionBadge", "level": "permissionLevel"},
    "jinja": {"macros": "macros.html", "badge": "permission_badge", "level": "permission_level"},
}

MARKDOWN_PREAMBLE = (
    "### Commands\n"
    "The command system is based on permission levels. A player will have a permission level\n"
    "of **0** by default. A player with level **1** can execute commands for level **1** and\n"
    "below. A level **2** player can execute level **2**, **1** and **0** commands, and so on.\n"
    "\n\n"
)

class docs(minqlxtended.Plugin):
    _qlx_docsFormat = minqlxtended.setting("qlx_docsFormat", "markdown")

    @minqlxtended.command("gendocs", permission=5, usage="[excluded_plugins]")
    def cmd_gendocs(self, player, msg, channel):
        """Generate a command list based on currently loaded plugins, as Markdown, Twig or Jinja."""
        wanted = self._qlx_docsFormat.lower()
        filename = FORMATS.get(wanted)
        if filename is None:
            channel.reply(f"^1qlx_docsFormat^7 is ^3{self._qlx_docsFormat}^7; it has to be one of ^6{', '.join(sorted(FORMATS))}^7.")
            return

        excluded = [name.lower() for name in msg[1:]] if len(msg) > 1 else []
        prefix = self.get_cvar("qlx_commandPrefix")
        commands = self.collect_commands(excluded)

        flavour = TEMPLATE_FLAVOURS.get(wanted)
        if flavour:
            out = self.render_template(commands, prefix, flavour)
        else:
            out = self.render_markdown(commands, prefix)

        with open(os.path.join(self.get_cvar("fs_basepath"), filename), "w") as handle:
            handle.write(out)

        channel.reply(f"^7Command list generated as ^6{filename}^7!")

    def collect_commands(self, excluded):
        """Every registered command, grouped by the permission level it needs."""
        commands = {}
        for cmd in minqlxtended.COMMANDS.commands:
            if cmd.plugin.__class__.__name__ in excluded:  # Skip excluded plugins.
                continue

            permission = cmd.permission
            override = minqlxtended.get_cvar("qlx_perm_" + cmd.name)
            if override:
                permission = cmd._permission_cvar("qlx_perm_" + cmd.name, override, cmd.permission)

            commands.setdefault(permission, []).append(cmd)

        return commands

    def command_name(self, cmd, prefix):
        """The command as a player types it, and its aliases the same way."""
        name = prefix + cmd.name if cmd.prefix else cmd.name
        aliases = [prefix + alias if cmd.prefix else alias for alias in cmd.aliases]
        return name, aliases

    def render_template(self, commands, prefix, flavour):
        """HTML with template conditionals, so a visitor only sees the commands they can run."""
        macros, badge, level = flavour["macros"], flavour["badge"], flavour["level"]
        out = f'{{% from "{macros}" import {badge} %}}\n'
        out += f"<p><small><em>Last updated:</em> {datetime.now().replace(microsecond=0)}</small></p>\n"
        for perm in sorted(commands):
            if perm:
                out += f"{{% if {level} >= {perm} %}}\n"

            out += f"<h3>Permission level <strong>{perm}</strong>: {{{{ {badge}({perm}) }}}}</h3>\n"
            out += "<ul>\n"
            for cmd in sorted(commands[perm], key=lambda x: x.plugin.__class__.__name__):
                name, aliases = self.command_name(cmd, prefix)
                out += "  <li>\n"
                out += f"    <code>{name}</code>"
                if aliases:
                    out += " (alternatively " + ", ".join(f"<code>{alias}</code>" for alias in aliases) + ")"
                out += f" from plug-in <em>{cmd.plugin.__class__.__name__}</em>.\n"

                # Docstring.
                if cmd.handler.__doc__:
                    out += f'    <p class="font-monospace">{escape(cmd.handler.__doc__.strip()).replace(linesep, "<br>")}</p>\n'

                # Usage
                if cmd.usage:
                    out += f"    <p><em>Usage</em>: <code>{name} {escape(cmd.usage.strip())}</code></p>\n"

                out += "  </li>\n"
            out += "</ul>\n"

            if perm:
                out += "{% endif %}\n"

        out += f'<em>Automatically generated by <a href="https://github.com/tjone270/minqlxtended">minqlxtended {minqlxtended.__version__} (with plug-ins {minqlxtended.plugins_version()}.)</a></em>'
        return out

    def render_markdown(self, commands, prefix):
        """Markdown, for a wiki page or a README."""
        out = MARKDOWN_PREAMBLE
        out += f"*Last updated: {datetime.now().replace(microsecond=0)}*\n\n"
        for perm in sorted(commands):
            out += f"*   Permission level **{perm}**\n\n"
            for cmd in sorted(commands[perm], key=lambda x: x.plugin.__class__.__name__):
                name, aliases = self.command_name(cmd, prefix)
                out += f"    *   **`{name}`**"
                if aliases:
                    out += " (alternatively " + ", ".join(f"`{alias}`" for alias in aliases) + ")"
                out += f" from *{cmd.plugin.__class__.__name__}*\n\n"

                if cmd.handler.__doc__:
                    docstring = " ".join(cmd.handler.__doc__.split())
                    out += f"        {docstring}\n\n"

                # Usage
                if cmd.usage:
                    out += f"        *Usage*: `{name} {cmd.usage.strip()}`\n\n"

        out += f"*Automatically generated by [minqlxtended {minqlxtended.__version__} (with plug-ins {minqlxtended.plugins_version()})](https://github.com/tjone270/minqlxtended)*"
        return out
