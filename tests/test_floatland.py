import copy
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from floatland.config import DEFAULTS, load
from floatland.controller import Controller, HIDDEN
from floatland.geometry import Rect, cascade, snap, workarea, ZONES
from floatland.ipc import Hyprland, IPCError, address, exchange
from floatland.state import State


def window(number=1, floating=False, name="1", **extra):
    return dict(address=f"0x{number:x}", pid=number, initialClass="app", initialTitle="original",
                **{"class": "app"}, workspace={"id": int(name) if name.isdecimal() else 5, "name": name},
                monitor=0, at=[100, 100], size=[700, 500], floating=floating,
                mapped=True, hidden=False, pinned=False, fullscreen=0, **extra)


MONITOR = dict(id=0, name="DP-1", x=0, y=0, width=1920, height=1080,
               scale=1, transform=0, reserved=[0, 32, 0, 0])


class FakeHyprland:
    def __init__(self, clients):
        self.clients = clients
        self.monitors = [copy.deepcopy(MONITOR)]
        self.focus = clients[0]["address"] if clients else None
        self.current = {"id": 1, "name": "1"}
        self.commands = []
        self.fail = None

    def query(self, name):
        return copy.deepcopy({
            "clients": self.clients, "monitors": self.monitors, "activeworkspace": self.current,
            "activewindow": next((c for c in self.clients if c["address"] == self.focus), {}),
        }[name])

    def dispatch(self, name, arguments):
        if name == self.fail:
            raise IPCError("simulated dispatcher failure")
        self.commands.append((name, arguments))
        target = arguments.split("address:")[-1]
        client = next(c for c in self.clients if c["address"] == target)
        if name in ("setfloating", "settiled"):
            client["floating"] = name == "setfloating"
        elif name in ("movewindowpixel", "resizewindowpixel"):
            values = [int(v) for v in arguments.split(",")[0].split()[1:]]
            client["at" if name == "movewindowpixel" else "size"] = values
        elif name == "movetoworkspacesilent":
            ws = arguments.split(",")[0].removeprefix("name:")
            client["workspace"] = {"id": -99 if ws.startswith("special:") else 1, "name": ws}
        elif name == "pinwindow":
            client["pinned"] = arguments.split(",")[0] == "enable"
        elif name == "focuswindow":
            self.focus = target
        elif name == "closewindow":
            self.clients.remove(client)
            if self.focus == target:
                self.focus = None


class GeometryTests(unittest.TestCase):
    def test_scaled_rotated_negative_monitor_and_panel(self):
        monitor = dict(MONITOR, width=3840, height=2160, scale=2, transform=1,
                       x=-1080, y=-100, reserved=[10, 40, 20, 30])
        self.assertEqual(workarea(monitor, 5), Rect(-1065, -55, 1040, 1840))

    def test_split_gap_and_bounds(self):
        bounds = Rect(-1230, 40, 1201, 807)
        left, right = snap(bounds, "left", 11), snap(bounds, "right", 11)
        self.assertEqual(right.x - (left.x + left.w), 11)
        for zone in ZONES:
            rect = snap(bounds, zone, 11)
            self.assertEqual(rect.fit(bounds), rect)

    def test_offscreen_restoration_and_tiny_output(self):
        self.assertEqual(Rect(-5000, 9999, 4000, 3000).fit(Rect(0, 0, 800, 600)),
                         Rect(0, 0, 800, 600))
        self.assertEqual(cascade(Rect(0, 0, 1, 1), 5), Rect(0, 0, 1, 1))


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = State(Path(self.temp.name) / "state.json")

    def tearDown(self):
        self.temp.cleanup()

    def controller(self, clients, **config):
        self.ipc = FakeHyprland(clients)
        self.manager = Controller(self.ipc, self.state, dict(DEFAULTS, **config))
        return self.manager

    def test_roundtrip_preserves_float_geometry_and_natural_dialog(self):
        manager = self.controller([window(), window(2, True)])
        manager.reconcile()
        self.ipc.clients[0]["at"], self.ipc.clients[0]["size"] = [222, 150], [900, 600]
        manager.command("mode", "tiling")
        self.assertFalse(self.ipc.clients[0]["floating"])
        self.assertTrue(self.ipc.clients[1]["floating"])
        manager.command("mode", "floating")
        self.assertEqual(self.ipc.clients[0]["at"], [222, 150])
        self.assertEqual(self.ipc.clients[0]["size"], [900, 600])
        self.assertEqual(self.ipc.clients[1]["at"], [100, 100])

    def test_only_current_workspace_changes_and_new_windows_follow_mode(self):
        manager = self.controller([window(), window(2, name="2")])
        manager.reconcile()
        manager.command("mode", "tiling")
        self.assertTrue(self.ipc.clients[1]["floating"])
        self.ipc.clients.extend([window(3), window(4, name="2")])
        manager.reconcile()
        self.assertFalse(self.ipc.clients[2]["floating"])
        self.assertTrue(self.ipc.clients[3]["floating"])

    def test_exclusions_special_pinned_fullscreen(self):
        clients = [window(i) for i in range(1, 5)]
        clients[0]["class"] = "ignore"
        clients[1]["workspace"]["id"] = -1
        clients[2]["pinned"] = True
        clients[3]["fullscreen"] = 2
        manager = self.controller(clients, exclude_classes=["^ignore$"])
        manager.reconcile()
        self.assertEqual(self.ipc.commands, [])
        self.ipc.clients[3]["fullscreen"] = 0
        manager.reconcile()
        self.assertTrue(self.ipc.clients[3]["floating"])

    def test_override_survives_mode_changes_and_auto_clears_it(self):
        manager = self.controller([window()])
        manager.reconcile()
        manager.command("window-toggle")
        self.assertFalse(self.ipc.clients[0]["floating"])
        manager.command("mode", "floating")
        self.assertFalse(self.ipc.clients[0]["floating"])
        manager.command("window-auto")
        self.assertTrue(self.ipc.clients[0]["floating"])

    def test_snap_restore_is_not_overwritten_by_second_snap(self):
        manager = self.controller([window(1, True)])
        manager.reconcile()
        manager.command("snap", "left")
        manager.command("snap", "top-right")
        manager.command("restore")
        self.assertEqual(self.ipc.clients[0]["at"], [100, 100])
        self.assertEqual(self.ipc.clients[0]["size"], [700, 500])

    def test_snap_of_tile_restores_tiling(self):
        manager = self.controller([window()], default_mode="tiling")
        manager.reconcile()
        manager.command("maximize")
        self.assertTrue(self.ipc.clients[0]["floating"])
        manager.command("maximize")
        self.assertFalse(self.ipc.clients[0]["floating"])

    def test_preview_saved_before_hiding_and_freed_after_restore(self):
        manager = self.controller([window()])
        manager.reconcile()
        captured = []
        self.ipc.remember_preview = lambda c, remember=True: captured.append(
            (c['address'], c['pid'], remember, self.ipc.clients[0]['workspace']['name']))
        manager.command("minimize")
        self.assertEqual(captured, [('0x1', 1, True, '1')])
        self.assertEqual(self.ipc.clients[0]['workspace']['name'], HIDDEN)
        manager.command("restore-minimized")
        self.assertEqual(captured[-1], ('0x1', 1, False, '1'))

    def test_failed_minimize_releases_unused_preview(self):
        manager = self.controller([window()])
        manager.reconcile()
        captured = []
        self.ipc.remember_preview = lambda c, remember=True: captured.append(remember)
        self.ipc.fail = "movetoworkspacesilent"
        with self.assertRaises(IPCError):
            manager.command("minimize")
        self.assertEqual(captured, [True, False])
        self.assertNotIn("minimized", State(self.state.path).data["windows"]["0x1"])

    def test_preview_failure_does_not_block_minimize_or_restore(self):
        manager = self.controller([window()])
        manager.reconcile()
        def fail(*args):
            raise IPCError('preview failed')
        self.ipc.remember_preview = fail
        with self.assertLogs('floatland', level='WARNING'):
            manager.command('minimize')
            manager.command('restore-minimized')
        self.assertEqual(self.ipc.clients[0]['workspace']['name'], '1')
        self.assertNotIn('minimized', manager.windows['0x1'])

    def test_restore_rejects_address_reuse_during_move(self):
        manager = self.controller([window()])
        manager.reconcile()
        manager.command('minimize')
        original = self.ipc.dispatch
        def dispatch(name, arguments):
            original(name, arguments)
            if name == 'movetoworkspacesilent':
                self.ipc.clients[0]['pid'] = 999
        self.ipc.dispatch = dispatch
        self.ipc.commands.clear()
        with self.assertRaises(ValueError):
            manager.command('restore-minimized')
        self.assertEqual([name for name, _ in self.ipc.commands], ['movetoworkspacesilent'])

    def test_repeated_snap_restore_minimize_and_restart(self):
        manager = self.controller([window(1, True)])
        manager.reconcile()
        initial = (list(self.ipc.clients[0]['at']), list(self.ipc.clients[0]['size']))
        for iteration in range(100):
            manager.command('snap', list(ZONES)[iteration % len(ZONES)])
            manager.command('minimize')
            manager = Controller(self.ipc, State(self.state.path), dict(DEFAULTS))
            manager.command('restore-minimized')
            manager.command('restore')
            self.assertEqual((self.ipc.clients[0]['at'], self.ipc.clients[0]['size']), initial)
            self.assertNotIn('zone', manager.windows['0x1'])
            self.assertNotIn('minimized', manager.windows['0x1'])

    def test_minimize_restart_restore(self):
        manager = self.controller([window()])
        manager.reconcile()
        manager.command("minimize")
        self.assertEqual(self.ipc.clients[0]["workspace"]["name"], HIDDEN)
        replacement = Controller(self.ipc, State(self.state.path), dict(DEFAULTS))
        replacement.command("restore-minimized")
        self.assertEqual(self.ipc.clients[0]["workspace"]["name"], "1")
        self.assertFalse("minimized" in replacement.windows["0x1"])

    def test_failed_minimize_removes_recovery_record(self):
        manager = self.controller([window()])
        manager.reconcile()
        self.ipc.fail = "movetoworkspacesilent"
        with self.assertRaises(IPCError):
            manager.command("minimize")
        self.assertNotIn("minimized", State(self.state.path).data["windows"]["0x1"])

    def test_move_between_workspace_modes(self):
        manager = self.controller([window()], workspace_modes={"2": "tiling"})
        manager.reconcile()
        self.ipc.clients[0]["workspace"] = {"id": 2, "name": "2"}
        manager.reconcile()
        self.assertFalse(self.ipc.clients[0]["floating"])

    def test_no_feedback_loop_and_cleanup_reused_address(self):
        manager = self.controller([window()])
        manager.reconcile()
        count = len(self.ipc.commands)
        manager.reconcile()
        self.assertEqual(len(self.ipc.commands), count)
        self.ipc.clients[0]["pid"] = 1234
        self.ipc.clients[0]["floating"] = False
        manager.reconcile()
        self.assertEqual(manager.windows["0x1"]["identity"][0], 1234)
        self.ipc.clients.clear()
        manager.reconcile()
        self.assertEqual(manager.windows, {})

    def test_release_recovers_minimized_and_original_flags(self):
        manager = self.controller([window(), window(2, True)])
        manager.reconcile()
        manager.command("minimize")
        manager.release()
        self.assertEqual(self.ipc.clients[0]["workspace"]["name"], "1")
        self.assertFalse(self.ipc.clients[0]["floating"])
        self.assertTrue(self.ipc.clients[1]["floating"])
        self.assertEqual(self.state.data["windows"], {})

    def test_negative_named_workspace_is_not_special(self):
        client = window(name="special-project")
        client["workspace"]["id"] = -1337
        manager = self.controller([client])
        self.ipc.current = {"id": -1337, "name": "special-project"}
        manager.reconcile()
        self.assertTrue(self.ipc.clients[0]["floating"])
        manager.command("toggle")
        self.assertFalse(self.ipc.clients[0]["floating"])
        manager.command("minimize")
        manager.command("restore-minimized")
        self.assertEqual(self.ipc.clients[0]["workspace"]["name"], "special-project")

    def test_real_special_workspace_is_not_managed(self):
        client = window(name="special:terminal")
        client["workspace"]["id"] = -99
        manager = self.controller([client])
        manager.reconcile()
        self.assertEqual(self.ipc.commands, [])

    def test_failed_placement_retains_original_flag_on_disk(self):
        manager = self.controller([window()])
        self.ipc.fail = "resizewindowpixel"
        with self.assertRaises(IPCError):
            manager.reconcile()
        self.assertTrue(self.ipc.clients[0]["floating"])
        self.assertFalse(State(self.state.path).data["windows"]["0x1"]["original_floating"])

    def test_release_rejects_fullscreen_before_any_mutation(self):
        manager = self.controller([window()])
        manager.reconcile()
        self.ipc.clients[0]["fullscreen"] = 2
        count = len(self.ipc.commands)
        with self.assertRaises(ValueError):
            manager.release()
        self.assertEqual(len(self.ipc.commands), count)
        self.assertIn("0x1", manager.windows)

    def test_close_acts_on_the_active_window_only(self):
        manager = self.controller([window(), window(2)])
        manager.reconcile()
        self.ipc.focus = "0x2"
        manager.command("close")
        self.assertEqual([c["address"] for c in self.ipc.clients], ["0x1"])
        self.assertEqual(self.ipc.commands[-1], ("closewindow", "address:0x2"))

    def test_close_refuses_pinned_windows(self):
        pinned = window()
        pinned["pinned"] = True
        manager = self.controller([pinned])
        with self.assertRaises(ValueError):
            manager.command("close")

    def test_pin_toggles_a_floating_window_and_unpins_it_again(self):
        floating = window()
        floating["floating"] = True
        manager = self.controller([floating])
        manager.command("pin")
        self.assertTrue(self.ipc.clients[0]["pinned"])
        self.assertEqual(self.ipc.commands[-1], ("pinwindow", "enable,address:0x1"))
        manager.command("pin")      # a pinned window is not "eligible", but must stay unpinnable
        self.assertFalse(self.ipc.clients[0]["pinned"])
        self.assertEqual(self.ipc.commands[-1], ("pinwindow", "disable,address:0x1"))

    def test_pin_refuses_tiled_windows(self):
        manager = self.controller([window()])
        with self.assertRaisesRegex(ValueError, "floating"):
            manager.command("pin")
        self.assertEqual(self.ipc.commands, [])

    def test_titlebar_snap_reserves_frame_at_internal_split(self):
        manager = self.controller([window()], titlebar_height=32)
        manager.reconcile()
        manager.command("snap", "bottom")
        expected = snap(workarea(MONITOR, 10), "bottom", 10)
        self.assertEqual(self.ipc.clients[0]["at"], [expected.x, expected.y + 32])
        self.assertEqual(self.ipc.clients[0]["size"], [expected.w, expected.h - 32])
        manager.command("maximize")
        self.assertEqual(self.ipc.clients[0]["at"][1], 32 + 10 + 32)


class PinRendering(unittest.TestCase):
    def test_lua_for_pin_and_rejection_of_other_actions(self):
        from floatland.ipc import dispatch_lua
        self.assertIn('hl.dsp.window.pin({window = w, action = "enable"})', dispatch_lua("pinwindow", "enable,address:0xab"))
        for bad in ("toggle", 'enable"}); os.exit() --', ""):
            with self.assertRaises(ValueError):
                dispatch_lua("pinwindow", bad + ",address:0xab")


class TransportTests(unittest.TestCase):
    def test_actual_unix_socket_fragmented_response(self):
        # macOS Unix socket paths are short; /tmp keeps this portable.
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            path = Path(directory) / ".socket.sock"
            received = []
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(path))
                server.listen()
                def serve():
                    conn, _ = server.accept()
                    with conn:
                        received.append(conn.recv(100))
                        conn.sendall(b'[{"id":')
                        conn.sendall(b'1}]')
                thread = threading.Thread(target=serve)
                thread.start()
                self.assertEqual(Hyprland(directory).query("monitors"), [{"id": 1}])
                thread.join(2)
            self.assertEqual(received, [b"j/monitors"])

    def test_bad_address_rejected(self):
        for value in ("active;exec evil", "", "0x123\n", None):
            with self.assertRaises(ValueError):
                address(value)

    def test_missing_socket_is_actionable_error(self):
        with self.assertRaises(IPCError):
            exchange("/tmp/floatland-nonexistent-socket", "x")


class ConfigTests(unittest.TestCase):
    def test_invalid_config_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for data in ({"gap": -1}, {"width": 2}, {"workspace_modes": []},
                         {"exclude_classes": ["["]}, {"typo": True}):
                path.write_text(json.dumps(data))
                with self.assertRaises((ValueError, __import__("re").error)):
                    load(path)

    def test_invalid_state_root_is_reported_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            for data in ('[]', 'null', '42'):
                path.write_text(data)
                with self.assertRaises(ValueError): State(path)
                self.assertEqual(path.read_text(), data)

    def test_atomic_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = State(path)
            state.data["modes"]["web"] = "tiling"
            state.save()
            self.assertEqual(State(path).data["modes"], {"web": "tiling"})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
