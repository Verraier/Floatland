import tempfile
import unittest
from pathlib import Path
from test_floatland import FakeHyprland, window
from floatland.controller import Controller
from floatland.config import DEFAULTS
from floatland.state import State

class BarsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ipc = FakeHyprland([window(1, True), window(2, True)])
        self.manager = Controller(self.ipc, State(Path(self.temp.name)/'state.json'), dict(DEFAULTS))

    def test_close_targets_unfocused_window(self):
        self.manager.bars_event('1,close,0x2,2,')
        self.assertEqual([c['address'] for c in self.ipc.clients], ['0x1'])

    def test_maximize_targets_unfocused_window(self):
        self.manager.bars_event('1,maximize,0x2,2,')
        self.assertEqual(self.ipc.clients[0]['size'], [700, 500])
        self.assertNotEqual(self.ipc.clients[1]['size'], [700, 500])

    def test_minimize_targets_unfocused_window(self):
        self.manager.bars_event('1,minimize,0x2,2,')
        self.assertEqual(self.ipc.clients[0]['workspace']['name'], '1')
        self.assertTrue(self.ipc.clients[1]['workspace']['name'].startswith('special:'))

    def test_pid_mismatch_rejected_without_dispatch(self):
        with self.assertRaises(ValueError):
            self.manager.bars_event('1,close,0x2,999,')
        self.assertEqual(self.ipc.commands, [])

    def test_closed_target_never_falls_back_to_focus(self):
        self.ipc.clients.pop()
        with self.assertRaises(ValueError):
            self.manager.bars_event('1,close,0x2,2,')
        self.assertEqual(self.ipc.commands, [])

    def test_bad_events_rejected_without_dispatch(self):
        for payload in ('', '2,close,0x2,2,', '1,exec,0x2,2,', '1,close,,2,',
                        '1,close,0x2,0,', '1,close,0x2,-2,', '1,snap,0x2,2,unknown',
                        '1,close,0x2,2,left', '1,close,0x2,2,,'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.manager.bars_event(payload)
        self.assertEqual(self.ipc.commands, [])

    def test_snap_targets_unfocused_window(self):
        self.manager.bars_event('1,snap,0x2,2,left')
        self.assertEqual(self.ipc.clients[0]['size'], [700, 500])
        self.assertEqual(self.manager.windows['0x2']['zone'], 'left')

    def test_tiling_and_exclusions_still_apply(self):
        self.ipc.clients[1]['pinned'] = True
        with self.assertRaises(ValueError):
            self.manager.bars_event('1,maximize,0x2,2,')
        self.assertEqual(self.ipc.commands, [])

    def test_drag_snap_restore_keeps_position_before_drag(self):
        original = [233, 177, 700, 500]
        self.ipc.clients[1]['at'] = original[:2]
        self.manager.bars_event('1,drag-start,0x2,2,233;177;700;500')
        self.ipc.clients[1]['at'] = [1100, 42]  # dropped near the palette
        self.manager.bars_event('1,snap,0x2,2,left')
        self.manager.command('restore', target='0x2', pid=2)
        self.assertEqual(self.ipc.clients[1]['at'] + self.ipc.clients[1]['size'], original)

    def test_drag_restored_then_resnap_uses_new_free_geometry(self):
        self.manager.bars_event('1,snap,0x2,2,left')
        self.manager.bars_event('1,drag-start,0x2,2,10;42;945;1028')
        self.manager.bars_event('1,drag-restored,0x2,2,330;240;700;500')
        self.assertNotIn('zone', self.manager.windows['0x2'])
        self.manager.bars_event('1,snap,0x2,2,right')
        self.manager.command('restore', target='0x2', pid=2)
        self.assertEqual(self.ipc.clients[1]['at'], [330, 240])
        self.assertEqual(self.ipc.clients[1]['size'], [700, 500])

    def test_plain_drag_does_not_poison_later_keyboard_snap(self):
        self.manager.bars_event('1,drag-start,0x2,2,100;100;700;500')
        self.ipc.clients[1]['at'] = [410, 280]
        self.manager.bars_event('1,drag-end,0x2,2,')
        self.manager.command('snap', 'left', target='0x2', pid=2)
        self.manager.command('restore', target='0x2', pid=2)
        self.assertEqual(self.ipc.clients[1]['at'], [410, 280])

    def test_repeated_snap_preserves_first_position(self):
        self.ipc.clients[1]['at'] = [210, 180]
        for zone in ('left', 'right', 'full'):
            self.manager.command('snap', zone, target='0x2', pid=2)
        self.manager.command('maximize', target='0x2', pid=2)
        self.assertEqual(self.ipc.clients[1]['at'], [210, 180])
        self.assertEqual(self.ipc.clients[1]['size'], [700, 500])

    def test_minimize_restore_keeps_offcenter_coordinates(self):
        self.ipc.clients[1]['at'] = [210, 180]
        self.manager.bars_event('1,minimize,0x2,2,')
        self.ipc.clients[1]['at'] = [500, 350]
        self.manager.command('restore-minimized')
        self.assertEqual(self.ipc.clients[1]['at'], [210, 180])

    def test_invalid_drag_payload_rejected(self):
        for value in ('1;2;0;500', '1;2;nan;500', '1;2;3', '1;2;-3;500'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.manager.bars_event('1,drag-start,0x2,2,' + value)
        self.assertEqual(self.ipc.commands, [])

    def test_restart_reapplies_policy_to_existing_window(self):
        self.manager.reconcile()
        self.ipc.clients[1]['floating'] = False  # changed while daemon was stopped
        restarted = Controller(self.ipc, State(self.manager.state.path), dict(DEFAULTS))
        restarted.reconcile()
        self.assertTrue(self.ipc.clients[1]['floating'])

    def test_restart_preserves_floating_geometry_and_snap_restore(self):
        self.ipc.clients[1]['at'] = [210, 180]
        self.manager.reconcile()
        self.manager.bars_event('1,snap,0x2,2,left')
        snapped = list(self.ipc.clients[1]['at']) + list(self.ipc.clients[1]['size'])
        restarted = Controller(self.ipc, State(self.manager.state.path), dict(DEFAULTS))
        restarted.reconcile()
        self.assertEqual(self.ipc.clients[1]['at'] + self.ipc.clients[1]['size'], snapped)
        restarted.command('restore', target='0x2', pid=2)
        self.assertEqual(self.ipc.clients[1]['at'], [210, 180])

    def test_restart_preserves_explicit_tiling_workspace_mode(self):
        self.ipc.clients[1]['floating'] = False
        self.manager.reconcile()
        self.manager.command('mode', 'tiling')
        restarted = Controller(self.ipc, State(self.manager.state.path), dict(DEFAULTS))
        restarted.reconcile()
        self.assertEqual(restarted.mode('1'), 'tiling')
        self.assertFalse(self.ipc.clients[1]['floating'])
