"""Hyprland's public Unix socket protocol; no shell command execution."""
import json
import os
from pathlib import Path
import re
import socket


class IPCError(RuntimeError):
    pass


def instance_dir():
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    if not signature or not runtime or "/" in signature or signature in (".", ".."):
        raise IPCError("Run inside Hyprland with HYPRLAND_INSTANCE_SIGNATURE and XDG_RUNTIME_DIR set")
    return Path(runtime) / "hypr" / signature


def exchange(path, payload, limit=16 * 1024 * 1024, timeout=3):
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(path))
            connection.sendall(payload.encode())
            chunks, size = [], 0
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    return b"".join(chunks).decode()
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise IPCError("IPC response exceeds size limit")
    except (OSError, UnicodeError) as error:
        raise IPCError(str(error)) from error


class Hyprland:
    def __init__(self, directory):
        self.directory = Path(directory)

    def query(self, name):
        try:
            return json.loads(exchange(self.directory / ".socket.sock", "j/" + name))
        except ValueError as error:
            raise IPCError("Invalid Hyprland JSON response: " + name) from error

    def dispatch(self, command, arguments):
        # Controller operation names are internal; never send legacy dispatch IPC.
        self.evaluate(dispatch_lua(command, arguments), command)

    def evaluate(self, source, operation="eval"):
        reply = exchange(self.directory / ".socket.sock", "/eval " + source)
        if reply.strip() != "ok":
            raise IPCError(f"{operation}: {reply.strip()}")

    def configure_appearance(self, settings):
        from .config import validate_appearance
        fields = []
        for key, value in validate_appearance(settings).items():
            fields.append(key + '=' + (lua_string(value) if isinstance(value, str) else ('true' if value else 'false') if type(value) is bool else str(value)))
        self.evaluate('local revision = hl.plugin.floatland.appearance({' + ','.join(fields) + '}); '
                      'assert(type(revision) == "number" and revision > 0, '
                      '"Native plugin did not acknowledge settings; restart with matching run.py")', 'appearance')

    def present_tasks(self, kind, windows, selected):
        from .icons import resolve
        entries = ','.join('{icon=' + lua_string(resolve(w.get('initialClass') or w.get('class', ''))) + ',address=' + lua_string(w['address']) + ',pid=' + str(int(w['pid'])) + '}' for w in windows)
        self.evaluate('assert(hl.plugin.floatland.tasks, "Floatland native task UI not loaded"); '
                      'hl.plugin.floatland.tasks(' + str(kind) + ',{' + entries + '},' + str(selected) + ')', 'task switcher')

    def prepare_switcher(self, generation):
        self.evaluate("hl.plugin.floatland.prepare_tab(" + str(int(generation)) + ")", "prepare switcher")

    def prepare_overview(self, generation):
        self.evaluate('hl.plugin.floatland.prepare_overview(' + str(int(generation)) + ')', 'prepare overview')

    def check_selection(self, generation):
        self.evaluate('assert(hl.plugin.floatland.selection_valid(' + str(int(generation)) +
                      '), "Overview selection expired")', 'validate overview selection')

    def finish_selection(self, generation, success):
        self.evaluate('hl.plugin.floatland.finish_selection(' + str(int(generation)) + ',' +
                      ('true' if success else 'false') + ')', 'finish overview selection')

    def remember_preview(self, client, remember=True):
        self.evaluate('if hl.plugin and hl.plugin.floatland and hl.plugin.floatland.remember_preview then '
                      'hl.plugin.floatland.remember_preview(' + lua_string(client['address']) + ',' +
                      str(int(client['pid'])) + ',' + ('true' if remember else 'false') + ') end',
                      'save minimized preview' if remember else 'forget minimized preview')

    def set_pip(self, w, enabled):
        self.evaluate('hl.plugin.floatland.pip(' + lua_string(w['address']) + ',' + str(int(w['pid']))
                      + ',' + ('true' if enabled else 'false') + ')', 'configure PiP')

    def raise_window(self, w):
        self.evaluate('hl.plugin.floatland.raise_window(' + lua_string(w['address']) + ',' + str(int(w['pid'])) + ')', 'raise task')

    def toggle_overview(self):
        # Visibility is toggled atomically by native tasks(mode=3).
        pass

    def close_overview(self):
        self.evaluate('if hl.plugin.floatland and hl.plugin.floatland.overview_active then '
                      'hl.plugin.floatland.overview_active(false) end', 'close overview')

    def poll_overview(self):
        # Native overview has no external provider whose state needs polling.
        pass

    def resync_bars(self):
        self.evaluate('if hl.plugin and hl.plugin.floatland and hl.plugin.floatland.refresh then '
                      'hl.plugin.floatland.refresh() end', 'refresh existing titlebars')

    def place_geometry(self, client, rect):
        target = address(client['address'])
        values = ','.join(str(int(v)) for v in rect.values())
        fallback = dispatch_lua('resizewindowpixel', f'exact {rect.w} {rect.h},{target}') + '; ' + dispatch_lua('movewindowpixel', f'exact {rect.x} {rect.y},{target}')
        self.evaluate('if hl.plugin and hl.plugin.floatland and hl.plugin.floatland.geometry and '
                      'hl.plugin.floatland.geometry(' + lua_string(client['address']) + ',' + str(int(client['pid'])) + ',' + values + ') then '
                      'else ' + fallback + ' end', 'place geometry')

    def sync_restore(self, client, saved):
        size = saved['geometry'][2:] if saved else [0, 0]
        self.evaluate('if hl.plugin and hl.plugin.floatland and hl.plugin.floatland.restore_size then '
                      'hl.plugin.floatland.restore_size(' + lua_string(client['address']) + ',' + str(int(client['pid'])) + ',' + ','.join(str(int(v)) for v in size) + ') end', 'sync restore size')

    def check_api(self):
        """Read-only probe before subscribing or modifying any windows."""
        try:
            self.evaluate(
                'assert(type(hl.get_window) == "function" and type(hl.dispatch) == "function" '
                'and type(hl.dsp.focus) == "function" '
                'and type(hl.dsp.window.float) == "function" '
                'and type(hl.dsp.window.resize) == "function" '
                'and type(hl.dsp.window.move) == "function", "missing Lua window API")')
        except IPCError as error:
            raise IPCError("Floatland requires Hyprland's Lua eval/window API (0.55+). "
                           "Run hyprctl version and floatland doctor. " + str(error)) from error


def lua_string(value):
    """Quote UTF-8 bytes with Lua decimal escapes, never JSON's unsupported \\u."""
    return '"' + "".join(chr(byte) if 32 <= byte < 127 and byte not in (34, 92)
                         else "\\%03d" % byte for byte in value.encode("utf-8")) + '"'


def dispatch_lua(command, arguments):
    """Translate the small internal operation vocabulary to addressed Lua actions."""
    params = ""
    if command in ("resizewindowpixel", "movewindowpixel", "movetoworkspacesilent", "pinwindow"):
        params, separator, target = arguments.rpartition(",")
        if not separator:
            raise ValueError("Missing window selector")
    else:
        target = arguments
    if not target.startswith("address:"):
        raise ValueError("An explicit window address is required")
    target = address(target[len("address:"):])
    if command in ("setfloating", "settiled"):
        action = "enable" if command == "setfloating" else "disable"
        expression = 'hl.dsp.window.float({window = w, action = "' + action + '"})'
    elif command in ("resizewindowpixel", "movewindowpixel"):
        match = re.fullmatch(r"exact (-?\d+) (-?\d+)", params)
        if not match:
            raise ValueError("Expected exact integer coordinates")
        x, y = map(int, match.groups())
        if command == "resizewindowpixel" and (x <= 0 or y <= 0):
            raise ValueError("Window dimensions must be positive")
        action = "resize" if command == "resizewindowpixel" else "move"
        expression = f"hl.dsp.window.{action}({{window = w, x = {x}, y = {y}, relative = false}})"
    elif command == "movetoworkspacesilent":
        if not params:
            raise ValueError("Missing workspace")
        expression = "hl.dsp.window.move({window = w, workspace = " + lua_string(params) + ", follow = false})"
    elif command == "pinwindow":
        if params not in ("enable", "disable"):
            raise ValueError("Pin action must be enable or disable")
        expression = 'hl.dsp.window.pin({window = w, action = "' + params + '"})'
    elif command == "focuswindow":
        expression = "hl.dsp.focus({window = w})"
    elif command == "closewindow":
        expression = "hl.dsp.window.close({window = w})"
    else:
        raise ValueError("Unsupported window operation: " + command)
    return ('local w = hl.get_window(' + lua_string(target) + '); '
            'assert(w, "Floatland: window no longer exists"); hl.dispatch(' + expression + ')')


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", value):
        raise ValueError("Invalid window address")
    return "address:" + value
