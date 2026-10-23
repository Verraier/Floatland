import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_floatland import FakeHyprland,window
from floatland.controller import Controller
from floatland.state import State
from floatland.config import DEFAULTS
from floatland.window_rules import Rules

class WindowRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)
        self.ipc=FakeHyprland([window(floating=True),window(2,floating=True)])
        self.calls=[]
        self.ipc.set_mini=lambda w,v:self.calls.append(('above',w['address'],v))
        self.ipc.set_pip=lambda w,v:self.calls.append(('above',w['address'],v))
        self.ipc.raise_window=lambda w:None
        self.ipc.menu_page=lambda rows:self.calls.append(('page',rows))
        self.c=Controller(self.ipc,State(self.path/'state.json'),copy.deepcopy(DEFAULTS))
        self.c.refresh()

    def test_settings_expand_rules_inline_without_navigation_pages(self):
        self.c.bars_event('1,settings,0x1,1,')
        rows=self.calls[-1][1]
        self.assertNotIn('windows-menu',[row['action'] for row in rows])
        self.assertEqual([row['address'] for row in rows if row['action']=='rules-menu'],['0x1','0x2'])
        self.c.bars_event('1,rules-menu,0x2,2,')
        rows=self.calls[-1][1]
        flags=[row for row in rows if row['action'].startswith('rule-')]
        self.assertTrue(flags)
        self.assertTrue(all(row['address']=='0x2' for row in flags))
        self.c.bars_event('1,rules-menu,0x2,2,')
        self.assertFalse(any(row['action'].startswith('rule-') for row in self.calls[-1][1]))

    def test_rule_is_exact_and_idempotent(self):
        w=self.c.clients[0]; w['title']='Picture-in-Picture'
        self.c.rules.set(w,'above',True)
        self.c.rules.apply(self.c); self.c.rules.apply(self.c)
        self.assertEqual(self.calls.count(('above','0x1',True)),1)
        self.assertTrue(self.c.windows['0x1']['above'])
        self.assertIsNone(self.c.rules.match(dict(w,title='Browser')))
        restored=Rules(self.path/'set-rules.json')
        self.assertTrue(restored.match(w)['above'])

    def test_menu_targets_original_window_and_saves_flag(self):
        self.ipc.focus='0x2'
        self.c.bars_event('1,rule-above,0x1,1,')
        self.assertTrue(self.c.windows['0x1']['above'])
        self.assertTrue(self.c.rules.match(self.c.clients[0])['above'])
        with self.assertRaises(ValueError): self.c.bars_event('1,rule-above,0x1,99,')

    def test_invalid_rules_leave_last_good_data(self):
        self.c.rules.set(self.c.clients[0],'above',True)
        (self.path/'set-rules.json').write_text('{"version":1,"global_integrated":false,"rules":[{"class":"a","title":"b","mini":"yes"}]}')
        with self.assertRaises(ValueError): self.c.rules.reload()
        self.assertTrue(self.c.rules.data['rules'][0]['above'])

