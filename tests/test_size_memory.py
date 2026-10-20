import copy
import tempfile
import unittest
from pathlib import Path
from floatland.config import DEFAULTS
from floatland.controller import Controller
from floatland.size_memory import SizeMemory
from floatland.state import State
from test_floatland import FakeHyprland, window


class SizeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.memory = SizeMemory(self.root / 'sizes.json')
        self.ipc = FakeHyprland([window(floating=True)])
        self.manager = Controller(self.ipc, State(self.root / 'session.json'), copy.deepcopy(DEFAULTS), self.memory)
        self.manager.reconcile()

    def tearDown(self):
        self.tmp.cleanup()

    def test_close_reopen_and_fresh_session_restore_size(self):
        self.ipc.clients[0]['size'] = [811, 613]
        self.manager.refresh()
        self.ipc.clients.clear()
        self.manager.reconcile()
        memory = SizeMemory(self.root / 'sizes.json')
        ipc = FakeHyprland([window(2)])
        manager = Controller(ipc, State(self.root / 'new-session.json'), copy.deepcopy(DEFAULTS), memory)
        manager.reconcile()
        self.assertEqual(ipc.clients[0]['size'], [811, 613])

    def test_snap_and_minimize_do_not_replace_normal_size(self):
        self.ipc.clients[0]['size'] = [811, 613]
        self.manager.command('snap', 'left')
        self.manager.refresh()
        self.assertEqual(self.memory.get(self.ipc.clients[0]), [811, 613])
        self.manager.command('minimize')
        self.manager.refresh()
        self.assertEqual(self.memory.get(self.ipc.clients[0]), [811, 613])

    def test_unchanged_other_window_does_not_win_each_sample(self):
        self.ipc.clients.append(window(2, floating=True))
        self.manager.reconcile()
        self.manager.refresh()
        self.ipc.clients[0]['size'] = [911, 650]
        self.manager.refresh()
        self.manager.refresh()
        self.assertEqual(self.memory.get(self.ipc.clients[0]), [911, 650])

    def test_disabled_does_not_restore(self):
        self.memory.remember(dict(self.ipc.clients[0], size=[900, 600]))
        self.manager.config['remember_sizes'] = False
        self.ipc.clients.append(window(2, floating=True))
        self.manager.reconcile()
        self.assertEqual(self.ipc.clients[1]['size'], [700, 500])

    def test_fullscreen_does_not_replace_normal_size(self):
        self.manager.refresh()
        self.ipc.clients[0].update(fullscreen=2, size=[1920, 1080])
        self.manager.refresh()
        self.assertEqual(self.memory.get(self.ipc.clients[0]), [700, 500])

    def test_bad_file_is_preserved(self):
        path = self.root / 'bad.json'
        path.write_text('{broken')
        with self.assertLogs('floatland', level='WARNING'):
            memory = SizeMemory(path)
        memory.remember(self.ipc.clients[0])
        memory.flush()
        self.assertEqual(path.read_text(), '{broken')

    def test_fit_to_smaller_monitor(self):
        self.memory.remember(dict(self.ipc.clients[0], size=[3000, 2000]))
        self.ipc.clients.append(window(2, floating=True))
        self.manager.reconcile()
        self.assertLessEqual(self.ipc.clients[1]['size'][0], 1920)
        self.assertLessEqual(self.ipc.clients[1]['size'][1], 1080)

    def test_xwayland_saved_helper_size_is_not_applied_or_overwritten(self):
        self.memory.remember(dict(self.ipc.clients[0], size=[80, 50]))
        self.ipc.clients.append(window(2, floating=True, xwayland=True))
        self.manager.reconcile()
        self.assertEqual(self.ipc.clients[1]['size'], [700, 500])
        self.ipc.clients[1]['size'] = [12, 12]
        self.manager.refresh()
        self.assertNotEqual(self.memory.get(self.ipc.clients[1]), [12, 12])

    def test_xwayland_memory_is_explicitly_opt_in(self):
        self.manager.refresh()
        self.manager.config['remember_xwayland_sizes'] = True
        self.memory.remember(dict(self.ipc.clients[0], size=[820, 610]))
        self.ipc.clients.append(window(2, floating=True, xwayland=True))
        self.manager.reconcile()
        self.assertEqual(self.ipc.clients[1]['size'], [820, 610])

    def test_override_redirect_menu_is_not_managed(self):
        self.ipc.clients.append(window(2, floating=False, xwayland=True, override_redirect=True))
        self.manager.reconcile()
        self.assertFalse(self.ipc.clients[1]['floating'])
        self.assertNotIn('0x2', self.manager.windows)
