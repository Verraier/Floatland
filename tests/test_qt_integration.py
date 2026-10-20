import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io
from floatland.config import DEFAULTS
from floatland.controller import Controller
from floatland.state import State
from test_floatland import FakeHyprland, window

ROOT = Path(__file__).resolve().parents[1]


class QtIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ipc = FakeHyprland([window(1, True), window(2, True)])
        self.ipc.clients[1]['class'] = 'org.example.App.floatland-csd-test'
        self.c = Controller(self.ipc, State(Path(self.temp.name)/'state.json'), dict(DEFAULTS, titlebar_height=32))
        self.c.reconcile()

    def request(self, **kwargs):
        value = {'action': 'minimize', 'class': self.ipc.clients[1]['class'], 'pid': 2}
        value.update(kwargs)
        return self.c.command('qt-action', value)

    def test_action_targets_clicked_window_not_focused_window(self):
        self.request()
        self.assertEqual(self.ipc.focus, '0x1')
        self.assertEqual(self.ipc.clients[0]['workspace']['name'], '1')
        self.assertEqual(self.ipc.clients[1]['workspace']['name'], 'special:floatland-minimized')

    def test_wrong_pid_and_unsupported_action_rejected(self):
        with self.assertRaises(ValueError):
            self.request(pid=777)
        with self.assertRaises(ValueError):
            self.request(action='exec')

    def test_no_extra_titlebar_space_for_client_decoration(self):
        normal = self.c.bounds(self.ipc.clients[0])
        client = self.c.bounds(self.ipc.clients[1])
        self.assertEqual(client.h, normal.h+32)

    def test_launcher_environment_is_local_and_keeps_existing_paths(self):
        path = ROOT/'integrations/qt/launch.py'
        if not path.exists():
            self.skipTest('Optional integration removed')
        spec = importlib.util.spec_from_file_location('qt_launcher', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = {'QT_PLUGIN_PATH': '/existing', 'QT_WAYLAND_DISABLED_INTERFACES': 'old'}
        env = module.child_environment(original, '/new', '/settings.json')
        self.assertEqual(original['QT_PLUGIN_PATH'], '/existing')
        self.assertEqual(env['QT_PLUGIN_PATH'], '/new:/existing')
        self.assertEqual(env['QT_WAYLAND_DISABLED_INTERFACES'], 'old,zxdg_decoration_manager_v1')
        self.assertEqual(env['QT_WAYLAND_DECORATION'], 'floatland')

    def test_firefox_rejected_before_build(self):
        path = ROOT/'integrations/qt/launch.py'
        if not path.exists():
            self.skipTest('Optional integration removed')
        spec = importlib.util.spec_from_file_location('qt_launcher_guard', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        with patch.object(module.subprocess, 'run') as build, contextlib.redirect_stderr(output):
            with self.assertRaises(SystemExit):
                module.main(['--', 'firefox'])
            build.assert_not_called()
        self.assertIn('does not use Qt decorations', output.getvalue())
