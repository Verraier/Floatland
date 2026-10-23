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
        self.ipc.set_pip=lambda w,enabled:self.calls.append(('above',w['address'],enabled))
        self.ipc.raise_window=lambda w:self.calls.append(('raise',w['address']))
        self.c=Controller(self.ipc,State(Path(self.folder.name)/'state.json'),copy.deepcopy(DEFAULTS))

    def test_menu_targets_owner_not_focus(self):
        self.ipc.focus='0x2'
        self.c.bars_event('1,pin-above,0x1,1,')
        self.assertEqual(self.calls, [('above','0x1',True), ('raise','0x1')])
        with self.assertRaises(ValueError): self.c.bars_event('1,pin-above,0x1,22,')

    def test_fullscreen_is_explicitly_addressed(self):
        lua=dispatch_lua('fullscreen','address:0x1')
        self.assertIn('window = w',lua)
        self.assertIn('mode = "fullscreen"',lua)

    def test_native_failure_does_not_mark_above_active(self):
        def fail(w, enabled): raise ValueError('plugin unavailable')
        self.ipc.set_pip = fail
        with self.assertRaises(ValueError): self.c.command('pin-above')
        self.assertFalse(self.c.windows['0x1'].get('above'))
        self.assertFalse(self.ipc.clients[0]['pinned'])

    def test_pin_menu_targets_owner_and_keeps_above(self):
        self.c.command('pin-above')
        self.ipc.focus='0x2'
        self.c.bars_event('1,pin,0x1,1,')
        self.assertTrue(self.ipc.clients[0]['pinned'])
        self.assertFalse(self.ipc.clients[1]['pinned'])
        self.c.command('pin-above',target='0x1',pid=1)
        self.assertTrue(self.ipc.clients[0]['pinned'])

    def test_menu_targets_hidden_controls_window(self):
        self.ipc.window_menu=lambda w:self.calls.append(('menu',w['address']))
        self.c.command('window-menu',target='0x2',pid=2)
        self.assertEqual(self.calls[-1],('menu','0x2'))

    def test_hover_settings_validation(self):
        from floatland.config import validate_appearance
        self.assertEqual(validate_appearance({'menu_delay':3})['menu_delay'],3)
        with self.assertRaises(ValueError): validate_appearance({'menu_delay':0})
        with self.assertRaises(ValueError): validate_appearance({'focus_click_only':'yes'})
