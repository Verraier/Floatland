import argparse
import asyncio
import json
import logging
import sys

from . import __version__
from .config import load
from .daemon import run
from .geometry import ZONES
from .ipc import Hyprland, IPCError, exchange, instance_dir


def daemon_request(directory, action, value=None):
    path = directory / "floatland.sock"
    try:
        return json.loads(exchange(path, json.dumps({"action": action, "value": value}) + "\n", timeout=12 if action == "reload" else 3))
    except IPCError as error:
        if isinstance(error.__cause__, (FileNotFoundError, ConnectionRefusedError)):
            raise IPCError(
                "No running Floatland daemon for this Hyprland session. "
                "Run 'python3 run.py' and leave that terminal open; "
                "run commands from a second terminal in the same Hyprland session. "
                f"Control socket: {path}"
            ) from error
        raise


def parser():
    root = argparse.ArgumentParser(description="Shell-independent floating + native tiling for Hyprland")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser('start', help='Start the unified session from this checkout')
    commands.add_parser('reload', help='Validate and reload Floatland configuration')
    configuration = commands.add_parser('config', help='Manage Lua settings without a compositor')
    configuration.add_argument('config_action', choices=['init', 'show', 'path', 'reference', 'format'])
    configuration.add_argument('--dir', dest='config_dir')
    daemon = commands.add_parser("daemon", help="Run in foreground; keep this terminal open and use a second terminal for commands")
    daemon.add_argument("--config")
    daemon.add_argument("--verbose", action="store_true")
    tab = commands.add_parser('alt-tab', help='Select next task; alt-tab-commit activates it')
    tab.add_argument('value', nargs='?', choices=['reverse'])
    for name in ('alt-tab-commit', 'alt-tab-cancel', 'overview'):
        commands.add_parser(name)
    mode = commands.add_parser("mode", help="Set current workspace mode")
    mode.add_argument("value", choices=["floating", "tiling"])
    snapping = commands.add_parser("snap", help="Snap active window; restore returns its previous geometry")
    snapping.add_argument("value", choices=ZONES)
    for name in ("toggle", "window-toggle", "window-auto", "maximize", "restore", "center",
                 "minimize", "close", "pin", "restore-minimized", "status", "doctor"):
        commands.add_parser(name)
    bars = commands.add_parser("titlebars", help="Legacy upstream hyprbars integration; use run.py for bundled native titlebars")
    actions = bars.add_subparsers(dest="titlebar_action", required=True)
    install = actions.add_parser("install", help="Fetch hyprbars: hyprpm (source, built by hyprpm) or a checksummed prebuilt .so")
    install.add_argument("--method", choices=["hyprpm", "file"], default="hyprpm")
    install.add_argument("--url", help="HTTPS URL of a prebuilt libhyprbars.so (method=file)")
    install.add_argument("--sha256", help="Required with --url: SHA-256 of the file")
    init = actions.add_parser("init", help="Write ~/.config/hypr/floatland-titlebars.lua (regenerated) and "
                                           "floatland-buttons.lua (yours: created once, never overwritten)")
    init.add_argument("--config")
    init.add_argument("--executable", help="Command the buttons run (default: the installed floatland)")
    init.add_argument("--dir", help="Target directory (default: ~/.config/hypr)")
    lua = actions.add_parser("lua", help="Print/write the Lua snippet that configures hyprbars for Floatland")
    lua.add_argument("--config")
    lua.add_argument("--executable", help="Command the buttons run (default: the installed floatland)")
    lua.add_argument("--output", help="Write to this file instead of stdout")
    actions.add_parser("status", help="Is hyprbars installed and loaded?")
    actions.add_parser("remove", help="Disable/unload hyprbars installed by Floatland")
    stop = commands.add_parser("stop")
    stop.add_argument("--restore", action="store_true", help="Recover minimized windows and original floating flags")
    return root


def main():
    args = parser().parse_args()
    try:
        if args.command == 'start':
            from .session import main as start_session
            sys.exit(start_session())
        if args.command == 'config':
            from .lua_config import config_home
            root = __import__('pathlib').Path(args.config_dir) if args.config_dir else config_home()
            if args.config_action == 'reference':
                from pathlib import Path
                for template in sorted((Path(__file__).parent/'defaults'/'config').glob('*.lua')):
                    print('-- config/' + template.name + '\n' + template.read_text())
            elif args.config_action == 'format':
                from .lua_config import format_migrated
                changed = format_migrated(root)
                print('Formatted migrated files (backups: *.before-format):\n' + '\n'.join(changed) if changed else 'No generated migration files to format.')
            elif args.config_action == 'path':
                print(root / 'init.lua')
            else:
                value = load(root / 'init.lua', create=args.config_action == 'init')
                print(str(root / 'init.lua') if args.config_action == 'init' else json.dumps(value, indent=2, ensure_ascii=False))
            return
        if args.command == "titlebars":
            from .titlebars import run_cli
            sys.exit(run_cli(args))
        directory = instance_dir()
        if args.command == "daemon":
            logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                                format="%(asctime)s %(levelname)s %(message)s")
            asyncio.run(run(directory, load(args.config), config_path=args.config))
        elif args.command == "doctor":
            ipc = Hyprland(directory)
            ipc.check_api()
            print(json.dumps({"version": ipc.query("version"), "monitors": ipc.query("monitors"),
                              "ipc_backend": "lua-eval",
                              "daemon_socket": (directory / "floatland.sock").exists()}, indent=2))
        else:
            value = "restore" if args.command == "stop" and args.restore else getattr(args, "value", None)
            reply = daemon_request(directory, args.command, value)
            if not reply["ok"]:
                raise IPCError(reply["error"])
            print(json.dumps(reply["result"], ensure_ascii=False))
    except (IPCError, OSError, ValueError) as error:
        print(f"floatland: {error}", file=sys.stderr)
        sys.exit(1)
