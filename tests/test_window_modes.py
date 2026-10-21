import copy
import tempfile
import unittest
from pathlib import Path
from test_floatland import FakeHyprland,window
from floatland.config import DEFAULTS
from floatland.controller import Controller
from floatland.state import State
from floatland.ipc import dispatch_lua

class WindowModes(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.ipc=FakeHyprland([window(floating=True),window(2,floating=True)])
        self.calls=[]
        self.ipc.set_mini=lambda w,enabled:self.calls.append(('mini',w['address'],enabled))
        self.ipc.set_pip=lambda w,enabled:self.calls.append(('above',w['address'],enabled))
        self.ipc.raise_window=lambda w:self.calls.append(('raise',w['address']))
        self.c=Controller(self.ipc,State(Path(self.folder.name)/'state.json'),copy.deepcopy(DEFAULTS))

    def test_pin_and_mini_independent_and_no_resize(self):
        size=list(self.ipc.clients[0]['size']); pos=list(self.ipc.clients[0]['at'])
        self.c.command('pin-above'); self.c.command('mini-mode')
        self.assertTrue(self.c.windows['0x1']['mini'])
        self.assertTrue(self.c.windows['0x1']['above'])
        self.c.command('mini-mode-off')
        self.assertFalse(self.c.windows['0x1']['mini'])
        self.assertTrue(self.ipc.clients[0]['pinned'])
        self.c.command('pin-above')
        self.assertFalse(self.ipc.clients[0]['pinned'])
        self.assertEqual(self.ipc.clients[0]['size'],size)
        self.assertEqual(self.ipc.clients[0]['at'],pos)

    def test_menu_targets_owner_not_focus(self):
        self.ipc.focus='0x2'
        self.c.bars_event('1,mini-mode,0x1,1,')
        self.assertEqual(self.calls[-1],('mini','0x1',True))
        with self.assertRaises(ValueError): self.c.bars_event('1,mini-mode,0x1,22,')

    def test_stop_restore_disables_mini_and_pin(self):
        self.c.command('pin-above'); self.c.command('mini-mode'); self.c.release()
        self.assertFalse(self.ipc.clients[0]['pinned'])
        self.assertIn(('mini','0x1',False),self.calls)

    def test_fullscreen_is_explicitly_addressed(self):
        lua=dispatch_lua('fullscreen','address:0x1')
        self.assertIn('window = w',lua)
        self.assertIn('mode = "fullscreen"',lua)

    def test_native_failure_does_not_mark_mini_active(self):
        def fail(w,enabled): raise ValueError('plugin unavailable')
        self.ipc.set_mini=fail
        with self.assertRaises(ValueError): self.c.command('mini-mode')
        self.assertFalse(self.c.windows['0x1'].get('mini'))

    def test_native_failure_does_not_mark_above_active(self):
        def fail(w, enabled): raise ValueError('plugin unavailable')
        self.ipc.set_pip = fail
        with self.assertRaises(ValueError): self.c.command('pin-above')
        self.assertFalse(self.c.windows['0x1'].get('above'))
        self.assertFalse(self.ipc.clients[0]['pinned'])
