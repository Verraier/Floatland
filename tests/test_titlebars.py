import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from floatland import titlebars
from floatland.config import DEFAULTS, load, validate_style
from floatland.titlebars import TitlebarError

try:
    import lupa
except ImportError:  # the Lua execution tests are skipped without it
    lupa = None

ROOT = Path(__file__).resolve().parents[1]
ELF = b"\x7fELF" + b"\0" * 64
CONFIG = dict(DEFAULTS, titlebar_height=32)


STUB = """
    log = {}
    local function rec(name) return function(...) log[#log + 1] = {name = name, args = {...}} end end
    hl = {on = rec("on"), exec_cmd = rec("exec_cmd"), config = rec("config"), env = rec("env"),
          window_rule = rec("window_rule"), plugin = {load = rec("plugin_load")}}
    function enable_plugin(names)
        hl.plugin.hyprbars = {}
        for _, n in ipairs(names) do hl.plugin.hyprbars[n] = rec(n) end
    end
    function make_rules_raise() hl.window_rule = function() error("unknown rule key") end end
"""


def to_python(value):
    if lupa.lua_type(value) != "table":
        return value
    items = {k: to_python(v) for k, v in value.items()}
    if items and all(isinstance(k, int) for k in items):
        return [items[i] for i in sorted(items)]
    return items


class Glue:
    """Runs generated Lua against a recording stub of `hl`, with a real package.path."""

    def __init__(self, user_lua=None, with_plugin=True, plugin_api=("add_button", "clear_buttons"),
                 rules_raise=False):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name)
        self.lua = lupa.LuaRuntime()
        self.lua.execute(STUB)
        self.lua.execute('package.path = "%s/?.lua;" .. package.path' % self.path)
        if user_lua is not None:
            self.write_user(user_lua)
        if with_plugin:
            self.lua.globals().enable_plugin(self.lua.table_from(list(plugin_api)))
        if rules_raise:
            self.lua.globals().make_rules_raise()

    def write_user(self, text):
        (self.path / "floatland-buttons.lua").write_text(text, encoding="utf-8")

    def run(self, text):
        self.lua.execute(text)
        return [to_python(entry) for entry in self.lua.globals().log.values()]

    def close(self):
        self.directory.cleanup()


def run_glue(text, **options):
    glue = Glue(**options)
    try:
        return glue.run(text)
    finally:
        glue.close()


def named(log, name):
    return [entry["args"][0] for entry in log if entry["name"] == name]


def bars_of(log):
    return named(log, "config")[0]["plugin"]["hyprbars"]


def render(config=CONFIG, executable="/usr/bin/floatland", record=None):
    return titlebars.render_lua(config, executable, record)


@unittest.skipIf(lupa is None, "pip install lupa to execute the generated Lua")
class GeneratedLua(unittest.TestCase):
    def test_defaults_configure_hyprbars_and_register_three_buttons(self):
        log = run_glue(render(record={"method": "hyprpm"}))
        self.assertEqual([e["name"] for e in log], [
            "on", "config", "clear_buttons", "add_button", "add_button", "add_button",
            "window_rule", "window_rule"])
        bars = bars_of(log)
        self.assertEqual((bars["bar_height"], bars["enabled"]), (32, True))
        self.assertEqual(bars["on_double_click"], "/usr/bin/floatland maximize")
        self.assertEqual([b["action"] for b in named(log, "add_button")],
                         ["/usr/bin/floatland close", "/usr/bin/floatland maximize",
                          "/usr/bin/floatland minimize"])

    def test_first_config_pass_without_the_plugin_only_registers_the_loader(self):
        log = run_glue(render(record={"method": "hyprpm"}), with_plugin=False)
        self.assertEqual([e["name"] for e in log], ["on"])

    def test_icons_appear_on_hover_by_default_and_can_be_always_visible(self):
        self.assertIs(bars_of(run_glue(render()))["icon_on_hover"], True)
        log = run_glue(render(), user_lua='return { icons = "always" }')
        self.assertIs(bars_of(log)["icon_on_hover"], False)

    def test_buttons_have_equal_space_above_and_below(self):
        for height, requested in ((32, None), (33, 20), (32, 99), (32, 3), (30, 17), (48, 25)):
            with self.subTest(height=height, requested=requested):
                user = "return {}" if requested is None else f"return {{ button_size = {requested} }}"
                log = run_glue(render(dict(CONFIG, titlebar_height=height)), user_lua=user)
                size = named(log, "add_button")[0]["size"]
                self.assertEqual((height - size) % 2, 0, f"margins differ: bar {height}, button {size}")
                self.assertTrue(8 <= size <= height - 2)

    def test_alignment_and_title_options(self):
        user = 'return { buttons_align = "left", title_align = "left", title = false, blur = true, padding = 12 }'
        bars = bars_of(run_glue(render(), user_lua=user))
        self.assertEqual((bars["bar_buttons_alignment"], bars["bar_text_align"], bars["bar_title_enabled"],
                          bars["bar_blur"], bars["bar_padding"]), ("left", "left", False, True, 12))

    def test_the_shipped_template_is_identical_to_having_no_file(self):
        self.assertEqual(run_glue(render()), run_glue(render(), user_lua=titlebars.USER_TEMPLATE))

    def test_user_buttons_replace_the_defaults(self):
        user = """return { buttons = {
            { icon = "x", color = "rgb(111111)", action = "close" },
            { icon = "s", color = "rgb(222222)", action = "snap left", fg_color = "rgb(ffffff)" },
            { icon = "n", color = "rgb(333333)", shell = "notify-send 'hi there'" },
        } }"""
        buttons = named(run_glue(render(), user_lua=user), "add_button")
        self.assertEqual([b["action"] for b in buttons],
                         ["/usr/bin/floatland close", "/usr/bin/floatland snap left", "notify-send 'hi there'"])
        self.assertEqual(buttons[1]["fg_color"], "rgb(ffffff)")
        self.assertEqual(buttons[0]["fg_color"], "rgb(1f1f28)")

    def test_every_documented_floatland_action_can_be_a_button(self):
        user = 'return { buttons = {' + ",".join(
            f'{{ icon = "i", color = "rgb(000000)", action = "{a}" }}'
            for a in ("close", "maximize", "minimize", "pin", "window-toggle", "snap left", "center")) + '} }'
        actions = [b["action"] for b in named(run_glue(render(), user_lua=user), "add_button")]
        self.assertEqual(len(actions), 7)

    def test_active_window_styling_rule(self):
        log = run_glue(render(), user_lua='return { active_color = "rgb(abcdef)", active_text_color = "rgb(123456)" }')
        rule = named(log, "window_rule")[0]
        self.assertIs(rule["match"]["focus"], True)
        self.assertEqual((rule["hyprbars:bar_color"], rule["hyprbars:title_color"]), ("rgb(abcdef)", "rgb(123456)"))

    def test_tiled_windows_get_no_bar(self):
        rule = named(run_glue(render()), "window_rule")[1]
        self.assertIs(rule["match"]["float"], False)
        self.assertIs(rule["hyprbars:no_bar"], True)

    def test_apps_with_their_own_header_can_be_excluded(self):
        user = 'return { own_header_classes = { "firefox", "org\\\\.gnome\\\\..*" } }'
        rule = named(run_glue(render(), user_lua=user), "window_rule")[2]
        self.assertEqual(rule["match"]["class"], "(?i)^(firefox|org\\.gnome\\..*)$")
        self.assertIs(rule["hyprbars:no_bar"], True)

    def test_toolkit_decoration_switches_set_environment_even_before_the_plugin_loads(self):
        log = run_glue(render(), user_lua="return { decorations = { gtk3 = true, qt = true } }", with_plugin=False)
        self.assertEqual([e["args"] for e in log if e["name"] == "env"],
                         [["GTK_CSD", "0"], ["QT_WAYLAND_DISABLE_WINDOWDECORATION", "1"]])
        self.assertEqual([e["args"] for e in run_glue(render()) if e["name"] == "env"], [])

    def test_double_click_can_be_disabled(self):
        self.assertNotIn("on_double_click", bars_of(run_glue(render(), user_lua='return { double_click = "" }')))

    def test_a_rejected_window_rule_never_undoes_the_buttons(self):
        log = run_glue(render(), rules_raise=True)
        self.assertEqual(len(named(log, "add_button")), 3)

    def test_old_plugin_without_clear_buttons_still_works(self):
        log = run_glue(render(), plugin_api=("add_button",))
        self.assertEqual(len(named(log, "add_button")), 3)

    def test_config_json_style_is_a_default_that_the_lua_file_overrides(self):
        config = dict(CONFIG, titlebar_style={"color": "rgba(11223344)", "font": "Inter", "font_size": 14})
        bars = bars_of(run_glue(render(config)))
        self.assertEqual((bars["bar_color"], bars["bar_text_font"], bars["bar_text_size"]),
                         ("rgba(11223344)", "Inter", 14))
        bars = bars_of(run_glue(render(config), user_lua='return { font = "Noto Sans" }'))
        self.assertEqual((bars["bar_color"], bars["bar_text_font"]), ("rgba(11223344)", "Noto Sans"))

    def test_edits_are_picked_up_when_the_config_is_reloaded(self):
        glue = Glue(user_lua='return { icons = "hover" }')
        try:
            text = render()
            self.assertIs(bars_of(glue.run(text))["icon_on_hover"], True)
            glue.write_user('return { icons = "always" }')
            glue.lua.execute("log = {}")
            glue.lua.globals().enable_plugin(glue.lua.table_from(["add_button", "clear_buttons"]))
            self.assertIs(bars_of(glue.run(text))["icon_on_hover"], False)
        finally:
            glue.close()

    def test_hostile_values_cannot_break_out_of_lua_strings(self):
        evil = "/tmp/we ird/\"); os.execute('x') --/флоат"
        log = run_glue(render(executable=evil, record={"method": "file", "path": '/p/"a"\\b.so'}))
        self.assertEqual(log[0]["name"], "plugin_load")
        self.assertEqual(log[0]["args"][0], '/p/"a"\\b.so')
        self.assertEqual(named(log, "add_button")[0]["action"], evil + " close")


@unittest.skipIf(lupa is None, "pip install lupa to execute the generated Lua")
class UserFileMistakes(unittest.TestCase):
    """A broken settings file must fail loudly, in terms the user can act on."""

    def assertRejected(self, user_lua, fragment):
        with self.assertRaises(lupa.LuaError) as caught:
            run_glue(render(), user_lua=user_lua)
        self.assertIn("floatland-buttons.lua", str(caught.exception))
        self.assertIn(fragment, str(caught.exception))

    def test_unknown_setting_is_reported_with_its_name(self):
        self.assertRejected("return { colour = 'x' }", "unknown setting 'colour'")

    def test_bad_choices(self):
        self.assertRejected('return { icons = "sometimes" }', "icons must be one of: hover, always")
        self.assertRejected('return { buttons_align = "middle" }', "buttons_align")
        self.assertRejected('return { title_align = "right" }', "title_align")

    def test_wrong_types(self):
        self.assertRejected('return { font_size = "big" }', "font_size must be a number")
        self.assertRejected('return { title = "yes" }', "title must be a boolean")
        self.assertRejected("return { buttons = 5 }", "buttons must be a table")

    def test_incomplete_buttons(self):
        self.assertRejected('return { buttons = { { color = "rgb(000000)", action = "close" } } }', "button #1")
        self.assertRejected('return { buttons = { { icon = "x", color = "rgb(000000)" } } }', "action")

    def test_decorations(self):
        self.assertRejected("return { decorations = { gtk5 = true } }", "unknown decorations.gtk5")
        self.assertRejected("return { decorations = true }", "decorations must be a table")

    def test_file_that_forgets_return(self):
        self.assertRejected("local x = 1", "return")

    def test_syntax_errors_surface_instead_of_silently_using_defaults(self):
        with self.assertRaises(lupa.LuaError) as caught:
            run_glue(render(), user_lua="return { icons = ")
        self.assertIn("floatland-buttons", str(caught.exception))


class RenderGuards(unittest.TestCase):
    def test_requires_a_bar_height(self):
        with self.assertRaises(TitlebarError):
            titlebars.render_lua(DEFAULTS, "floatland")

    def test_loader_lines_match_the_install_method(self):
        self.assertIn("hyprpm reload -n", render(record={"method": "hyprpm"}))
        self.assertIn("hl.plugin.load", render(record={"method": "file", "path": "/x.so"}))
        plain = render(record=None)
        self.assertNotIn("hyprpm", plain)
        self.assertNotIn("plugin.load", plain)

    def test_generated_file_is_portable_across_lua_versions(self):
        text = render() + titlebars.USER_TEMPLATE
        self.assertNotIn("\\u{", text)            # Lua 5.3+ only; LuaJIT rejects it
        self.assertNotIn("goto ", text)
        text.encode("utf-8")


class InitCommand(unittest.TestCase):
    def test_writes_both_files_and_never_overwrites_the_users_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            first = titlebars.init(CONFIG, "/opt/fl", None, directory)
            self.assertTrue(first["created_buttons_file"])
            mine = Path(first["buttons"])
            mine.write_text('return { icons = "always" } -- my edit', encoding="utf-8")
            Path(first["glue"]).write_text("stale", encoding="utf-8")
            second = titlebars.init(CONFIG, "/opt/fl", None, directory)
            self.assertFalse(second["created_buttons_file"])
            self.assertIn("my edit", mine.read_text(encoding="utf-8"))
            self.assertIn("local EXE", Path(second["glue"]).read_text(encoding="utf-8"))

    def test_nothing_is_written_when_the_config_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TitlebarError):
                titlebars.init(DEFAULTS, "/opt/fl", None, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    @unittest.skipIf(lupa is None, "pip install lupa")
    def test_written_files_work_together_from_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            titlebars.init(CONFIG, "/opt/fl", None, directory)
            lua = lupa.LuaRuntime()
            lua.execute(STUB)
            lua.execute('package.path = "%s/?.lua;" .. package.path' % directory)
            lua.globals().enable_plugin(lua.table_from(["add_button", "clear_buttons"]))
            lua.execute('require("floatland-titlebars")')
            self.assertEqual(len(to_python(lua.globals().log)), 7)   # config, clear, 3 buttons, 2 rules


class StyleConfig(unittest.TestCase):
    def test_validation(self):
        self.assertEqual(validate_style({}), {})
        for bad in ({"colour": "x"}, {"color": "red"}, {"color": 'rgb(ffffff)"'}, {"font": ""},
                    {"font": "a\nb"}, {"font_size": 3}, {"font_size": True}, []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_style(bad)

    def test_config_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "c.json"
            path.write_text(json.dumps({"titlebar_height": 30, "titlebar_style": {"font_size": 13}}))
            self.assertEqual(load(path)["titlebar_style"], {"font_size": 13})


class FileInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self.temp.name
        self.digest = hashlib.sha256(ELF).hexdigest()

    def tearDown(self):
        if self.old is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self.old
        self.temp.cleanup()

    def written(self):
        directory = titlebars.data_dir()
        return sorted(p.name for p in directory.iterdir()) if directory.exists() else []

    def test_success_verifies_then_stores_with_safe_permissions(self):
        result = titlebars.install_file("https://example.org/lib.so", self.digest.upper(), fetch=lambda u: ELF)
        target = Path(result["path"])
        self.assertEqual(target.read_bytes(), ELF)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
        self.assertEqual(titlebars.read_record()["sha256"], self.digest)
        self.assertEqual(self.written(), sorted([target.name, "hyprbars.json"]))

    def test_checksum_mismatch_writes_nothing(self):
        with self.assertRaisesRegex(TitlebarError, "mismatch"):
            titlebars.install_file("https://example.org/l.so", "0" * 64, fetch=lambda u: ELF)
        self.assertEqual(self.written(), [])

    def test_refuses_without_checksum_or_over_plain_http(self):
        for url, digest in (("https://x/l.so", None), ("https://x/l.so", "abc"),
                            ("http://x/l.so", self.digest), ("file:///etc/passwd", self.digest), (None, self.digest)):
            with self.subTest(url=url, digest=digest), self.assertRaises(TitlebarError):
                titlebars.install_file(url, digest, fetch=lambda u: self.fail("must not download"))

    def test_non_elf_is_rejected_even_with_a_matching_checksum(self):
        data = b"#!/bin/sh\necho pwned\n"
        with self.assertRaisesRegex(TitlebarError, "ELF"):
            titlebars.install_file("https://x/l.so", hashlib.sha256(data).hexdigest(), fetch=lambda u: data)
        self.assertEqual(self.written(), [])

    def test_download_errors_become_titlebar_errors(self):
        def boom(url):
            raise OSError("network down")
        with self.assertRaisesRegex(TitlebarError, "network down"):
            titlebars.install_file("https://x/l.so", self.digest, fetch=boom)

    def test_failed_unload_preserves_binary_and_record(self):
        result = titlebars.install_file("https://x/l.so", self.digest, fetch=lambda u: ELF)
        for code, message in ((1, 'failed'), (0, 'plugin unload failed')):
            with self.subTest(code=code):
                with self.assertRaises(TitlebarError):
                    titlebars.remove(run=lambda *a, **k: SimpleNamespace(returncode=code, stdout=message, stderr=''))
                self.assertTrue(Path(result['path']).exists())
                self.assertEqual(titlebars.read_record()['method'], 'file')

    def test_status_and_remove(self):
        result = titlebars.install_file("https://x/l.so", self.digest, fetch=lambda u: ELF)
        calls = []

        def run(command, **kwargs):
            calls.append(command)
            return SimpleNamespace(returncode=0, stdout="ok" if "unload" in command else "Plugin hyprbars by Hypr", stderr="")
        state = titlebars.status(run=run)
        self.assertTrue(state["loaded"])
        self.assertEqual(state["installed"]["method"], "file")
        titlebars.remove(run=run)
        self.assertIn(["hyprctl", "plugin", "unload", result["path"]], calls)
        self.assertFalse(Path(result["path"]).exists())
        self.assertEqual(titlebars.read_record(), {})
        with self.assertRaises(TitlebarError):
            titlebars.remove(run=run)


class HyprpmInstall(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self.temp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self.old
        self.temp.cleanup()

    def runner(self, listing="", fail_on=None):
        self.calls = []

        def run(command, **kwargs):
            self.calls.append(command)
            code = 1 if command == fail_on else 0
            return SimpleNamespace(returncode=code, stdout=listing, stderr="")
        return run

    def test_official_sequence_and_prompts_are_not_swallowed(self):
        titlebars.install_hyprpm(run=self.runner(), which=lambda n: "/usr/bin/hyprpm")
        self.assertEqual(self.calls, [
            ["hyprpm", "list"], ["hyprpm", "update"], ["hyprpm", "add", titlebars.REPOSITORY],
            ["hyprpm", "enable", "hyprbars"], ["hyprpm", "reload", "-n"]])
        self.assertEqual(titlebars.read_record()["method"], "hyprpm")

    def test_repository_already_added_is_not_added_twice(self):
        titlebars.install_hyprpm(run=self.runner(listing="Repository hyprland-plugins"),
                                 which=lambda n: "/usr/bin/hyprpm")
        self.assertNotIn(["hyprpm", "add", titlebars.REPOSITORY], self.calls)

    def test_failure_stops_and_records_nothing(self):
        with self.assertRaises(TitlebarError):
            titlebars.install_hyprpm(run=self.runner(fail_on=["hyprpm", "enable", "hyprbars"]),
                                     which=lambda n: "/usr/bin/hyprpm")
        self.assertEqual(titlebars.read_record(), {})

    def test_missing_hyprpm_has_an_actionable_message(self):
        with self.assertRaisesRegex(TitlebarError, "method file"):
            titlebars.install_hyprpm(run=self.runner(), which=lambda n: None)


class CommandLine(unittest.TestCase):
    def cli(self, *arguments, data=None):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), XDG_DATA_HOME=data or tempfile.gettempdir())
        for key in ("HYPRLAND_INSTANCE_SIGNATURE", "XDG_RUNTIME_DIR"):
            env.pop(key, None)    # these commands must work outside a Hyprland session
        return subprocess.run([sys.executable, "-m", "floatland", "titlebars", *arguments],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)

    def test_lua_command_writes_a_file_without_hyprland(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "c.json"
            config.write_text(json.dumps({"titlebar_height": 32}))
            output = Path(directory) / "bars.lua"
            done = self.cli("lua", "--config", str(config), "--executable", "/opt/fl", "--output", str(output),
                            data=directory)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn('local EXE = "/opt/fl"', output.read_text(encoding="utf-8"))

    def test_init_command_creates_the_settings_file_in_the_chosen_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "c.json"
            config.write_text(json.dumps({"titlebar_height": 32}))
            target = Path(directory) / "hypr"
            done = self.cli("init", "--config", str(config), "--executable", "/opt/fl", "--dir", str(target),
                            data=directory)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertTrue((target / "floatland-buttons.lua").exists())
            self.assertIn('require("floatland-titlebars")', done.stderr)

    def test_lua_command_explains_missing_height(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "c.json"
            config.write_text("{}")
            done = self.cli("lua", "--config", str(config), "--executable", "x", data=directory)
            self.assertEqual(done.returncode, 1)
            self.assertIn("titlebar_height", done.stderr)

    def test_file_install_needs_a_checksum(self):
        done = self.cli("install", "--method", "file", "--url", "https://example.org/x.so")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--sha256", done.stderr)

    def test_url_flags_require_the_file_method(self):
        done = self.cli("install", "--url", "https://example.org/x.so")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--method file", done.stderr)


if __name__ == "__main__":
    unittest.main()
