import copy
import tempfile
import unittest
from pathlib import Path
from test_floatland import FakeHyprland, window
from floatland.controller import Controller
from floatland.config import DEFAULTS
from floatland.state import State

class PiPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ipc = FakeHyprland([window(floating=True), window(2, floating=True)])
        self.ipc.set_pip = lambda w, enabled: None
        self.raised = []
        self.ipc.raise_window = lambda w: self.raised.append(w['address'])
        self.c = Controller(self.ipc, State(Path(self.tmp.name)/'state.json'), copy.deepcopy(DEFAULTS))

    def test_enter_raise_without_focus_and_restore(self):
        original = copy.deepcopy(self.ipc.clients[0])
        self.assertTrue(self.c.command('pip')['pip'])
        self.assertTrue(self.ipc.clients[0]['pinned'])
        self.assertLess(self.ipc.clients[0]['size'][0], original['size'][0])
        self.ipc.focus = '0x2'
        self.c.pip.raise_all()
        self.assertEqual(self.ipc.focus, '0x2')
        self.assertEqual(self.raised[-1], '0x1')
        self.c.bars_event('1,maximize,0x1,1,')
        self.assertFalse(self.ipc.clients[0]['pinned'])
        self.assertEqual(self.ipc.clients[0]['size'], original['size'])
        self.assertEqual(self.ipc.clients[0]['at'], original['at'])

    def test_restart_and_release_recover_pip(self):
        self.c.command('pip')
        self.c = Controller(self.ipc, self.c.state, copy.deepcopy(DEFAULTS))
        self.c.reconcile()
        self.assertTrue(self.c.pip.active(self.ipc.clients[0]))
        self.c.release()
        self.assertFalse(self.ipc.clients[0]['pinned'])

    def test_pip_never_enters_size_memory(self):
        self.c.command('pip')
        self.assertFalse(self.c.size_memory_allowed(self.ipc.clients[0]))

    def test_stale_pid_and_closed_window(self):
        self.c.command('pip')
        with self.assertRaises(ValueError):
            self.c.bars_event('1,pip,0x1,999,')
        self.ipc.clients.pop(0)
        self.c.reconcile()
        self.assertNotIn('0x1',self.c.windows)

    def test_minimize_exits_pip_before_hiding(self):
        self.c.command('pip')
        self.c.command('minimize')
        self.assertFalse(self.ipc.clients[0]['pinned'])
        self.assertNotIn('pip',self.c.windows['0x1'])
        self.assertIn('minimized',self.c.windows['0x1'])

    def test_other_workspace_mode_does_not_resize_pip(self):
        self.c.command('pip')
        size = list(self.ipc.clients[0]['size'])
        self.c.command('mode','tiling')
        self.assertEqual(self.ipc.clients[0]['size'], size)
        self.assertTrue(self.ipc.clients[0]['floating'])
