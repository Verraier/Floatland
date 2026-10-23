"""End-to-end daemon and CLI against real Unix sockets, without a compositor."""
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from test_floatland import FakeHyprland, window

ROOT = Path(__file__).resolve().parents[1]


class DaemonTests(unittest.TestCase):
    def test_daemon_cli_events_singleton_and_recovery(self):
        self.run_scenario()

    def test_unsupported_api_exits_without_retry_or_window_changes(self):
        self.run_scenario(lua_supported=False)

    def run_scenario(self, lua_supported=True):
        with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
            base = Path(temporary)
            directory = base / "hypr" / "test"
            directory.mkdir(parents=True)
            config_path = base / 'init.lua'
            config_path.write_text('return {}')
            fake = FakeHyprland([window()])
            received = []
            done = threading.Event()
            event_connected = threading.Event()
            event_connection = []
            listeners, threads = [], []
            for name in (".socket.sock", ".socket2.sock"):
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                listener.bind(str(directory / name))
                listener.listen()
                listener.settimeout(.1)
                listeners.append(listener)

            def requests():
                while not done.is_set():
                    try:
                        conn, _ = listeners[0].accept()
                    except socket.timeout:
                        continue
                    with conn:
                        request = conn.recv(8192).decode()
                        received.append(request)
                        if request.startswith("j/"):
                            result = json.dumps(fake.query(request[2:]))
                        elif request.startswith("/eval assert("):
                            result = "ok" if lua_supported else "unknown request: eval"
                        elif request.startswith("/eval if hl.plugin"):
                            # No native plugin in this fake compositor. Execute the
                            # geometry fallback; restore-size synchronization is a no-op.
                            if 'hl.plugin.floatland.geometry(' in request:
                                target = re.search(r'hl.get_window\("(address:0x[0-9a-f]+)"\)', request).group(1)
                                operations = re.findall(r'hl.dsp.window.(resize|move)\(\{window = w, x = (-?\d+), y = (-?\d+), relative = false', request)
                                if len(operations) != 2:
                                    raise AssertionError('Expected resize and absolute move fallback')
                                for operation, x, y in operations:
                                    fake.dispatch('resizewindowpixel' if operation == 'resize' else 'movewindowpixel', f'exact {x} {y},{target}')
                            result = 'ok'
                        elif request.startswith("/eval local w =") or request.startswith("/eval if not (hl.plugin"):
                            # Parse only the documented action subset, independently of
                            # the production encoder. Legacy dispatch is rejected below.
                            target = re.search(r'hl.get_window\("(address:0x[0-9a-f]+)"\)', request).group(1)
                            if "hl.dsp.window.float(" in request:
                                name = "setfloating" if 'action = "enable"' in request else "settiled"
                                args = target
                            elif "workspace =" in request:
                                name = "movetoworkspacesilent"
                                workspace = re.search(r'workspace = "([^"]+)"', request).group(1)
                                args = workspace + "," + target
                            elif "relative = false" in request:
                                name = "resizewindowpixel" if "window.resize(" in request else "movewindowpixel"
                                x, y = re.search(r'x = (-?\d+), y = (-?\d+)', request).groups()
                                args = f"exact {x} {y},{target}"
                            else:
                                name, args = "focuswindow", target
                            fake.dispatch(name, args)
                            result = "ok"
                        else:
                            result = "error: old syntax; dispatch in lua is a shorthand for hl.dispatch(...)"
                        conn.sendall(result.encode())

            def events():
                while not done.is_set():
                    try:
                        conn, _ = listeners[1].accept()
                    except socket.timeout:
                        continue
                    event_connection.append(conn)
                    event_connected.set()
                    done.wait()
                    conn.close()

            for target in (requests, events):
                thread = threading.Thread(target=target, daemon=True)
                thread.start()
                threads.append(thread)

            env = dict(os.environ, XDG_RUNTIME_DIR=str(base), HYPRLAND_INSTANCE_SIGNATURE="test")
            def cli(*args):
                return subprocess.run([sys.executable, "run.py", *args], cwd=ROOT,
                                      env=env, capture_output=True, text=True, timeout=6)

            def wait_for(predicate):
                end = time.monotonic() + 5
                while time.monotonic() < end:
                    if predicate():
                        return
                    time.sleep(.02)
                self.fail("Timed out waiting for daemon state")

            process = subprocess.Popen([sys.executable, "run.py", "daemon", "--config", str(config_path)], cwd=ROOT,
                                       env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                if not lua_supported:
                    process.wait(5)
                    _, stderr = process.communicate()
                    self.assertNotEqual(process.returncode, 0)
                    self.assertIn("requires Hyprland's Lua", stderr)
                    self.assertEqual(len(received), 1)
                    self.assertEqual(fake.commands, [])
                    return
                self.assertTrue(event_connected.wait(5))
                wait_for(lambda: fake.clients[0]["floating"])
                listed=cli('windows')
                self.assertEqual(listed.returncode,0,listed.stderr)
                self.assertEqual(json.loads(listed.stdout)['api_version'],1)
                config_path.write_text('return {windows={default_mode="tiling"}}')
                reloaded = cli('reload')
                self.assertEqual(reloaded.returncode, 0, reloaded.stderr)
                self.assertFalse(fake.clients[0]['floating'])
                config_path.write_text('return {}')
                self.assertEqual(cli('reload').returncode, 0)
                self.assertTrue(fake.clients[0]['floating'])
                config_path.write_text('return {windows={gap=-1}}')
                self.assertNotEqual(cli('reload').returncode, 0)
                self.assertTrue(fake.clients[0]['floating'])
                config_path.write_text('return {}')
                duplicate = cli("daemon")
                self.assertNotEqual(duplicate.returncode, 0)
                self.assertIn("already running", duplicate.stderr)
                result = cli("toggle")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["mode"], "tiling")
                self.assertFalse(fake.clients[0]["floating"])
                event_connection[0].sendall(b"floatland_log>>warning,test native warning\n")
                fake.clients.append(window(2))
                event_connection[0].sendall(b"openwindow>>2,1,app,title\n")
                wait_for(lambda: json.loads(cli("status").stdout)["managed_windows"] == 2)
                self.assertFalse(fake.clients[1]["floating"])
                self.assertEqual(cli("mode", "floating").returncode, 0)
                self.assertEqual(cli("snap", "left").returncode, 0)
                self.assertEqual(cli("restore").returncode, 0)
                self.assertEqual(cli("minimize").returncode, 0)
                self.assertEqual(fake.clients[0]["workspace"]["id"], -99)
                self.assertEqual(cli("restore-minimized").returncode, 0)
                self.assertEqual(cli("minimize").returncode, 0)
                result = cli("stop", "--restore")
                self.assertEqual(result.returncode, 0, result.stderr)
                process.wait(5)
                self.assertEqual(process.returncode, 0)
                self.assertFalse(fake.clients[0]["floating"])
                self.assertEqual(fake.clients[0]["workspace"]["name"], "1")
                _, logs = process.communicate()
                self.assertIn("WARNING Native: test native warning", logs)
                self.assertIn("Config applied (manual)", logs)
                self.assertFalse((directory / "floatland.sock").exists())
                self.assertTrue(any(r.startswith("/eval local") for r in received))
                self.assertFalse(any(r.startswith("/dispatch") for r in received))
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(5)
                process.communicate()
                done.set()
                for thread in threads:
                    thread.join(2)
                for listener in listeners:
                    listener.close()
