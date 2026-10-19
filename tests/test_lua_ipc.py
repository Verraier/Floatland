"""Regression coverage for the runtime legacy-dispatch failure reported on 0.1.0."""
import unittest
from unittest.mock import patch

from floatland.ipc import Hyprland, IPCError, dispatch_lua, lua_string


class LuaIPCTests(unittest.TestCase):
    def test_all_operations_use_addressed_lua_eval(self):
        cases = [
            ("setfloating", "address:0xabc", 'window.float({window = w, action = "enable"})'),
            ("settiled", "address:0xabc", 'window.float({window = w, action = "disable"})'),
            ("resizewindowpixel", "exact 800 600,address:0xabc",
             "window.resize({window = w, x = 800, y = 600, relative = false})"),
            ("movewindowpixel", "exact -1920 40,address:0xabc",
             "window.move({window = w, x = -1920, y = 40, relative = false})"),
            ("movetoworkspacesilent", "special:floatland-minimized,address:0xabc",
             'window.move({window = w, workspace = "special:floatland-minimized", follow = false})'),
            ("movetoworkspacesilent", "name:work,address:0xabc",
             'workspace = "name:work", follow = false'),
            ("focuswindow", "address:0xabc", "hl.dsp.focus({window = w})"),
        ]
        for command, args, expected in cases:
            with self.subTest(command=command, args=args):
                with patch("floatland.ipc.exchange", return_value="ok") as transport:
                    Hyprland("/tmp").dispatch(command, args)
                payload = transport.call_args.args[1]
                self.assertTrue(payload.startswith('/eval local w = hl.get_window("address:0xabc");'))
                self.assertIn(expected, payload)
                self.assertNotIn("/dispatch", payload)

    def test_lua_errors_surface_without_falling_back_to_old_dispatch(self):
        with patch("floatland.ipc.exchange", return_value="error: bad action") as transport:
            with self.assertRaisesRegex(IPCError, "bad action"):
                Hyprland("/tmp").dispatch("setfloating", "address:0xabc")
            self.assertEqual(transport.call_count, 1)

    def test_api_probe_is_read_only(self):
        with patch("floatland.ipc.exchange", return_value="ok") as transport:
            Hyprland("/tmp").check_api()
        payload = transport.call_args.args[1]
        self.assertTrue(payload.startswith("/eval assert("))
        self.assertNotIn("hl.dispatch(", payload)

    def test_untrusted_values_cannot_break_lua_string(self):
        self.assertEqual(lua_string('"\\\n'), '"\\034\\092\\010"')
        quoted = lua_string("Работа")
        self.assertNotIn("\\u", quoted)
        self.assertTrue(quoted.isascii())
        expression = dispatch_lua("movetoworkspacesilent", 'name:a"); error("bad"),address:0xabc')
        self.assertIn('workspace = "name:a\\034); error(\\034bad\\034)"', expression)

    def test_malformed_arguments_fail_before_transport(self):
        for command, argument in [
            ("setfloating", "active"),
            ("setfloating", "address:0xabc;evil()"),
            ("movewindowpixel", "exact 0;evil() 0,address:0xabc"),
            ("resizewindowpixel", "exact -1 2,address:0xabc"),
            ("exec", "address:0xabc"),
        ]:
            with self.subTest(command=command, argument=argument), patch("floatland.ipc.exchange") as transport:
                with self.assertRaises(ValueError):
                    Hyprland("/tmp").dispatch(command, argument)
                transport.assert_not_called()
