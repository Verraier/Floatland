"""Titlebars through the *upstream* hyprbars plugin.

The unified session ships its own native plugin. This legacy module is not used
by run.py; it only (1) fetches the official upstream plugin
and (2) generates the Lua that points its buttons at Floatland's own commands.

Two ways to obtain the plugin (Hyprland plugins are tied to the exact ABI of the
running compositor, so there is no universal binary):

* ``hyprpm``  - the official route. hyprpm downloads the pinned plugin sources
  and compiles them for your Hyprland in its own cache, outside this project.
* ``file``    - a prebuilt ``.so`` you choose: HTTPS only, SHA-256 mandatory,
  verified before anything is written. Hyprland itself still checks the ABI.

A plugin runs inside the compositor with full privileges, so Floatland never
chooses a binary source for you.
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

from .config import load
from .ipc import lua_string

REPOSITORY = "https://github.com/hyprwm/hyprland-plugins"
MAX_PLUGIN_BYTES = 64 * 1024 * 1024


class TitlebarError(RuntimeError):
    pass


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    return Path(base) / "floatland" / "plugins"


def record_path():
    return data_dir() / "hyprbars.json"


def read_record():
    try:
        value = json.loads(record_path().read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_record(value):
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    temporary = record_path().with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    os.replace(temporary, record_path())


# --------------------------------------------------------------------------
# Lua generation
# --------------------------------------------------------------------------
GLUE_FILE = "floatland-titlebars.lua"     # generated, safe to regenerate
USER_FILE = "floatland-buttons.lua"       # yours, never overwritten
USER_MODULE = "floatland-buttons"

GLUE_BODY = r'''
local function copy(t) local c = {} for k, v in pairs(t) do c[k] = v end return c end
local function fail(message) error("floatland-buttons.lua: " .. message, 0) end

local defaults = {
    color = "rgb(2a2a37)", text_color = "rgb(dcd7ba)",
    active_color = "rgb(363646)", active_text_color = "rgb(dcd7ba)",
    font = "Sans", font_size = 12, font_weight = 400,
    title = true, title_align = "center", blur = false, padding = 8,
    buttons_align = "right", button_padding = 6,
    icons = "hover", inactive_button_color = "rgb(3a3a4a)",
    double_click = "maximize",
    own_header_classes = {},
    decorations = { gtk3 = false, qt = false },
    buttons = {
        { name = "close",    icon = "×", color = "rgb(e46876)", action = "close" },
        { name = "maximize", icon = "□", color = "rgb(98bb6c)", action = "maximize" },
        { name = "minimize", icon = "–", color = "rgb(e6c384)", action = "minimize" },
    },
}
local known = copy(defaults)
known.button_size = true

local function read_user()
    package.loaded["floatland-buttons"] = nil      -- pick up edits on config reload
    local ok, result = pcall(require, "floatland-buttons")
    if ok then
        if type(result) ~= "table" then fail("the file must end with `return { ... }`") end
        return result
    end
    if tostring(result):find("module 'floatland-buttons' not found", 1, true) then return {} end
    error(result, 0)
end

local s = copy(defaults)
for k, v in pairs(LEGACY) do s[k] = v end
for k, v in pairs(read_user()) do
    if known[k] == nil then fail("unknown setting '" .. tostring(k) .. "'") end
    if k == "decorations" then
        if type(v) ~= "table" then fail("decorations must be a table") end
        local merged = copy(defaults.decorations)
        for dk, dv in pairs(v) do
            if defaults.decorations[dk] == nil then fail("unknown decorations." .. tostring(dk)) end
            merged[dk] = dv
        end
        s.decorations = merged
    else
        s[k] = v
    end
end

local function one_of(name, allowed)
    for _, v in ipairs(allowed) do if s[name] == v then return end end
    fail(name .. " must be one of: " .. table.concat(allowed, ", "))
end
local function kind(name, expected)
    if s[name] ~= nil and type(s[name]) ~= expected then fail(name .. " must be a " .. expected) end
end
one_of("icons", { "hover", "always" })
one_of("buttons_align", { "right", "left" })
one_of("title_align", { "center", "left" })
for _, name in ipairs({ "color", "text_color", "active_color", "active_text_color", "font",
                        "inactive_button_color", "double_click" }) do kind(name, "string") end
for _, name in ipairs({ "font_size", "font_weight", "padding", "button_padding", "button_size" }) do kind(name, "number") end
for _, name in ipairs({ "title", "blur" }) do kind(name, "boolean") end
kind("own_header_classes", "table")
kind("buttons", "table")

local function command_for(button)
    if button.shell ~= nil then return tostring(button.shell) end
    if button.action ~= nil then return EXE .. " " .. tostring(button.action) end
    fail("every button needs `action` (a floatland command) or `shell`")
end
for index, button in ipairs(s.buttons) do
    if type(button) ~= "table" or type(button.icon) ~= "string" or type(button.color) ~= "string" then
        fail("button #" .. index .. " needs `icon` and `color` strings")
    end
    command_for(button)
end

-- Equal space above and below the buttons: (bar height - button size) must be even.
local size = s.button_size or (HEIGHT - 12)
size = math.floor(math.max(8, math.min(size, HEIGHT - 2)))
if (HEIGHT - size) % 2 == 1 then size = size - 1 end

-- Ask toolkits not to draw their own header where they honour it. This is applied when an
-- app *starts*, to every app of that toolkit, whatever the workspace mode is.
if s.decorations.gtk3 then hl.env("GTK_CSD", "0") end
if s.decorations.qt then hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1") end

local function rule(definition) pcall(hl.window_rule, definition) end

-- The plugin registers after the config is parsed and asks for a reload; the first pass
-- therefore sees no plugin and stops here.
if hl.plugin and hl.plugin.hyprbars then
    local bars = {
        enabled = true, bar_height = HEIGHT, bar_color = s.color, col = { text = s.text_color },
        bar_text_font = s.font, bar_text_size = s.font_size, bar_text_weight = s.font_weight,
        bar_text_align = s.title_align, bar_title_enabled = s.title, bar_blur = s.blur,
        bar_padding = s.padding, bar_button_padding = s.button_padding,
        bar_buttons_alignment = s.buttons_align, icon_on_hover = (s.icons == "hover"),
        inactive_button_color = s.inactive_button_color,
        bar_part_of_window = true, bar_precedence_over_border = true,
    }
    if s.double_click ~= "" then bars.on_double_click = EXE .. " " .. s.double_click end
    hl.config({ plugin = { hyprbars = bars } })
    if hl.plugin.hyprbars.clear_buttons then hl.plugin.hyprbars.clear_buttons() end
    for _, button in ipairs(s.buttons) do
        hl.plugin.hyprbars.add_button({
            bg_color = button.color, fg_color = button.fg_color or "rgb(1f1f28)", size = size,
            icon = button.icon, action = command_for(button),
        })
    end
    -- Rules go last and are protected: a key this plugin version lacks must not undo the above.
    rule({ name = "floatland-titlebar-active", match = { focus = true },
           ["hyprbars:bar_color"] = s.active_color, ["hyprbars:title_color"] = s.active_text_color })
    rule({ name = "floatland-titlebar-floating-only", match = { float = false }, ["hyprbars:no_bar"] = true })
    if #s.own_header_classes > 0 then
        rule({ name = "floatland-own-header",
               match = { class = "(?i)^(" .. table.concat(s.own_header_classes, "|") .. ")$" },
               ["hyprbars:no_bar"] = true })
    end
end
'''

USER_TEMPLATE = r'''-- Floatland titlebar settings. This file is yours: Floatland never overwrites it.
-- Hyprland re-reads it on `hyprctl reload`. Delete any line to get its default.
-- The bar height is set in ~/.config/floatland/config.json ("titlebar_height") because
-- snap and maximize must reserve exactly the same space.
return {
    -- Bar
    color = "rgb(2a2a37)",             -- unfocused window
    text_color = "rgb(dcd7ba)",
    active_color = "rgb(363646)",      -- focused window
    active_text_color = "rgb(dcd7ba)",
    font = "Sans",
    font_size = 12,
    font_weight = 400,
    title = true,                      -- show the window title
    title_align = "center",            -- "center" | "left"
    blur = false,                      -- needs blur enabled globally in Hyprland
    padding = 8,                       -- left/right edge padding

    -- Buttons
    buttons_align = "right",           -- "right" | "left"
    -- button_size = 20,               -- circle diameter; default: bar height - 12. Kept so that the
                                       -- space above and below the circle is equal.
    button_padding = 6,                -- gap between buttons
    icons = "hover",                   -- "hover": glyph appears under the cursor | "always"
    inactive_button_color = "rgb(3a3a4a)",
    double_click = "maximize",         -- floatland command for a double click on the bar; "" = none

    -- First button is the one nearest to the edge. `action` is any `floatland <action>`;
    -- use `shell` instead to run an arbitrary command. `fg_color` tints the glyph.
    buttons = {
        { name = "close",    icon = "×", color = "rgb(e46876)", action = "close" },
        { name = "maximize", icon = "□", color = "rgb(98bb6c)", action = "maximize" },
        { name = "minimize", icon = "–", color = "rgb(e6c384)", action = "minimize" },
        -- { name = "pin",     icon = "●", color = "rgb(7e9cd8)", action = "pin" },
        -- { name = "tile",    icon = "▣", color = "rgb(957fb8)", action = "window-toggle" },
        -- { name = "left",    icon = "◧", color = "rgb(7fb4ca)", action = "snap left" },
        -- { name = "notes",   icon = "N",        color = "rgb(ffa066)", shell = "notify-send hello" },
    },

    -- Apps that draw their own header (browsers, GNOME apps...): no Floatland bar on them,
    -- otherwise they would have two. Regular expressions, matched against the window class.
    own_header_classes = {
        -- "firefox", "org\\.gnome\\..*",
    },

    -- Ask toolkits not to draw their own header, where they honour it. Applied when an
    -- app starts and to every app of that toolkit, also in tiling mode. GTK4, Electron and
    -- browsers ignore these; they have their own switch (e.g. "system title bar").
    decorations = {
        gtk3 = false,                  -- GTK_CSD=0
        qt = false,                    -- QT_WAYLAND_DISABLE_WINDOWDECORATION=1
    },
}
'''


def default_executable():
    found = shutil.which("floatland")
    if found:
        return shlex.quote(found)
    return shlex.quote(sys.executable) + " -m floatland"


def hypr_dir():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "hypr"


def render_lua(config, executable, record=None):
    """The generated glue between Floatland and hyprbars. Pure: easy to test and regenerate."""
    height = config["titlebar_height"]
    if height <= 0:
        raise TitlebarError("Set titlebar_height (for example 32) in the Floatland config first: "
                            "snap and maximize must reserve the same space the bar uses.")
    method = (record or {}).get("method")
    legacy = config.get("titlebar_style", {})
    pairs = []
    for key in ("color", "text_color", "font"):
        if key in legacy:
            pairs.append(f"{key} = {lua_string(legacy[key])}")
    if "font_size" in legacy:
        pairs.append(f"font_size = {int(legacy['font_size'])}")
    out = ["-- Generated by `floatland titlebars init`. Regenerate instead of editing; put your",
           f"-- own settings in {USER_FILE} next to this file.",
           f'-- Load it once from hyprland.lua:  require("{GLUE_FILE[:-4]}")', ""]
    if method == "file":
        out += ["hl.plugin.load(" + lua_string(record["path"]) + ")", ""]
    elif method == "hyprpm":
        out += ['hl.on("hyprland.start", function() hl.exec_cmd("hyprpm reload -n") end)', ""]
    out += [f"local EXE = {lua_string(executable)}",
            f"local HEIGHT = {int(height)}",
            "local LEGACY = { " + ", ".join(pairs) + " }" if pairs else "local LEGACY = {}"]
    return "\n".join(out) + "\n" + GLUE_BODY


def init(config, executable, record=None, directory=None):
    """Write the glue file (always) and the user's settings file (only if missing)."""
    directory = Path(directory) if directory else hypr_dir()
    directory.mkdir(parents=True, exist_ok=True)
    glue = directory / GLUE_FILE
    user = directory / USER_FILE
    text = render_lua(config, executable, record)    # may raise before anything is written
    created = not user.exists()
    if created:
        user.write_text(USER_TEMPLATE, encoding="utf-8")
    glue.write_text(text, encoding="utf-8")
    return {"glue": str(glue), "buttons": str(user), "created_buttons_file": created}


# --------------------------------------------------------------------------
# Installing the plugin
# --------------------------------------------------------------------------
def install_hyprpm(run=subprocess.run, which=shutil.which):
    """Official route. hyprpm keeps its own cache and may ask you to confirm."""
    if not which("hyprpm"):
        raise TitlebarError("hyprpm was not found. It ships with Hyprland; install it, or use "
                            "--method file with a prebuilt plugin you trust.")
    listing = run(["hyprpm", "list"], capture_output=True, text=True)
    steps = [["hyprpm", "update"]]
    if "hyprland-plugins" not in (listing.stdout or ""):
        steps.append(["hyprpm", "add", REPOSITORY])
    steps += [["hyprpm", "enable", "hyprbars"], ["hyprpm", "reload", "-n"]]
    for step in steps:   # not captured: hyprpm may prompt on the terminal
        if run(step).returncode != 0:
            raise TitlebarError("`" + " ".join(step) + "` failed; re-run it with -v for details")
    write_record({"method": "hyprpm", "repository": REPOSITORY})
    return {"method": "hyprpm"}


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "floatland"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_PLUGIN_BYTES + 1)
    if len(data) > MAX_PLUGIN_BYTES:
        raise TitlebarError("Plugin file is larger than %d MiB" % (MAX_PLUGIN_BYTES >> 20))
    return data


def install_file(url, sha256, fetch=download):
    """Prebuilt route: verify first, write second, load never (see `lua`)."""
    if urllib.parse.urlparse(url or "").scheme != "https":
        raise TitlebarError("--url must be an https:// address")
    expected = (sha256 or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise TitlebarError("--sha256 is required: the 64 hex digits published with the file")
    try:
        data = fetch(url)
    except (OSError, ValueError) as error:
        raise TitlebarError("Download failed: " + str(error)) from error
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise TitlebarError(f"Checksum mismatch: expected {expected}, got {digest}. Nothing was written.")
    if not data.startswith(b"\x7fELF"):
        raise TitlebarError("The file is not a shared library (no ELF header). Nothing was written.")
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"libhyprbars-{digest[:12]}.so"
    handle, temporary = tempfile.mkstemp(dir=str(directory), suffix=".part")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    write_record({"method": "file", "path": str(target), "sha256": digest, "url": url})
    return {"method": "file", "path": str(target)}


# --------------------------------------------------------------------------
# Inspecting / removing
# --------------------------------------------------------------------------
def hyprctl(*arguments, run=subprocess.run):
    try:
        done = run(["hyprctl", *arguments], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        raise TitlebarError("hyprctl failed: " + str(error)) from error
    return done.returncode, (done.stdout + done.stderr).strip()


def status(run=subprocess.run):
    record = read_record()
    code, listing = hyprctl("plugin", "list", run=run)
    return {"installed": record or None,
            "loaded": code == 0 and "hyprbars" in listing.lower(),
            "hyprctl_ok": code == 0}


def remove(run=subprocess.run, which=shutil.which):
    record = read_record()
    if not record:
        raise TitlebarError("Nothing installed by Floatland (no record found).")
    if record.get("method") == "hyprpm":
        if not which("hyprpm"):
            raise TitlebarError("hyprpm not found; installation record retained")
        for step in (["hyprpm", "disable", "hyprbars"], ["hyprpm", "reload", "-n"]):
            if run(step).returncode != 0:
                raise TitlebarError("Could not disable hyprbars; installation record retained")
    elif record.get("method") == "file":
        code, message = hyprctl("plugin", "unload", record["path"], run=run)
        if code != 0 or message.strip() != "ok":
            raise TitlebarError("Could not unload hyprbars; file and record retained: " + message)
        Path(record["path"]).unlink(missing_ok=True)
    else:
        raise TitlebarError("Invalid plugin installation record")
    record_path().unlink()
    return {"removed": record["method"]}


# --------------------------------------------------------------------------
# CLI glue
# --------------------------------------------------------------------------
def run_cli(args):
    try:
        action = args.titlebar_action
        if action == "install":
            if args.method == "file":
                result = install_file(args.url, args.sha256)
            elif args.url or args.sha256:
                raise TitlebarError("--url/--sha256 need --method file")
            else:
                result = install_hyprpm()
            print(json.dumps(result))
            print("Next: set \"titlebar_height\" in the Floatland config, then run "
                  "`floatland titlebars init`.", file=sys.stderr)
        elif action in ("lua", "init"):
            executable = args.executable or default_executable()
            if not args.executable and not shutil.which("floatland"):
                print("floatland: warning: 'floatland' is not on PATH; buttons will call "
                      f"'{sys.executable} -m floatland', which only works if that interpreter "
                      "can import it from any directory. Install it or pass --executable.",
                      file=sys.stderr)
            if action == "init":
                result = init(load(args.config), executable, read_record(), args.dir)
                print(json.dumps(result, indent=2))
                print('Add this line to hyprland.lua, then run `hyprctl reload`:\n'
                      '    require("floatland-titlebars")\n'
                      f"Your settings: {result['buttons']}", file=sys.stderr)
                return 0
            text = render_lua(load(args.config), executable, read_record())
            if args.output:
                Path(args.output).expanduser().write_text(text, encoding="utf-8")
                print("wrote " + str(Path(args.output).expanduser()))
            else:
                print(text)
        elif action == "status":
            print(json.dumps(status(), indent=2))
        elif action == "remove":
            print(json.dumps(remove()))
        return 0
    except (TitlebarError, ValueError, OSError) as error:
        print(f"floatland: {error}", file=sys.stderr)
        return 1
