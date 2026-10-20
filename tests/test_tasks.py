import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from test_floatland import FakeHyprland, window
from floatland.controller import Controller
from floatland.config import DEFAULTS
from floatland.state import State
from floatland import overview
from floatland.ipc import IPCError

class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ipc = FakeHyprland([window(1, True), window(2, True), window(3, True)])
        self.c = Controller(self.ipc, State(Path(self.temp.name)/'state.json'), dict(DEFAULTS))
        self.c.reconcile(); self.ipc.commands.clear()
        self.ipc.present_tasks = Mock()
        self.ipc.close_overview = Mock()
        self.ipc.raise_window = Mock()
        self.ipc.toggle_overview = Mock()
        self.ipc.check_selection = Mock()
        self.ipc.finish_selection = Mock()

    def test_overview_order_is_alphabetic_then_size_not_mru(self):
        self.ipc.clients[0].update(initialClass='zebra', size=[700, 500])
        self.ipc.clients[1].update(initialClass='Alpha', size=[600, 400])
        self.ipc.clients[2].update(initialClass='alpha', size=[900, 700])
        self.c.refresh()
        self.c.tasks.focused('0x1')
        self.c.tasks.overview()
        order = [w['address'] for w in self.ipc.present_tasks.call_args.args[1]]
        self.assertEqual(order, ['0x3', '0x2', '0x1'])
        self.c.tasks.focused('0x2')
        self.c.tasks.overview()
        self.assertEqual([w['address'] for w in self.ipc.present_tasks.call_args.args[1]], order)
        self.assertEqual(self.ipc.commands, [])

    def test_overview_uses_minimized_saved_size_for_order(self):
        self.c.command('minimize', target='0x2', pid=2)
        self.c.windows['0x2']['minimized']['geometry'] = [0, 0, 1200, 900]
        self.ipc.clients[1]['size'] = [1, 1]
        self.c.tasks.overview()
        self.assertEqual(self.ipc.present_tasks.call_args.args[1][0]['address'], '0x2')

    def test_tab_after_mouse_hover_continues_from_hovered_window(self):
        self.c.tasks.next()
        self.assertEqual(self.ipc.focus,'0x1')
        self.assertEqual(self.c.tasks.next_from('0x3',3)['selected'],'0x1')
        self.assertEqual(self.ipc.focus,'0x1')
        self.assertEqual(self.c.tasks.next_from('0x3',3,True)['selected'],'0x2')

    def test_mouse_step_does_not_reuse_closed_or_other_workspace_window(self):
        self.c.tasks.next()
        self.ipc.clients.pop()
        self.assertTrue(self.c.tasks.next_from('0x3',3)['cancelled'])
        self.assertEqual(self.ipc.focus,'0x1')

    def test_disabled_interfaces_do_not_select_or_open(self):
        self.c.config['appearance'] = {'switching_enabled': False, 'overview_enabled': False}
        self.assertTrue(self.c.tasks.next()['disabled'])
        self.assertEqual(self.c.tasks.overview(), {'overview': 'disabled'})
        self.assertEqual(self.ipc.commands, [])
        self.ipc.present_tasks.assert_called_once_with(0, [], 0)

    def test_overview_selection_ack_after_restore_and_raise(self):
        self.c.command('minimize', target='0x2', pid=2)
        def ack(generation, success):
            self.assertEqual((generation, success), (7, True))
            self.assertNotIn('minimized', self.c.windows['0x2'])
            self.assertEqual(self.ipc.focus, '0x2')
            self.ipc.raise_window.assert_called_once()
        self.ipc.finish_selection.side_effect = ack
        self.c.tasks.choose('0x2', 2, 7)
        self.ipc.close_overview.assert_not_called()
        self.ipc.present_tasks.assert_not_called()

    def test_overview_selection_failure_acknowledged(self):
        self.ipc.clients.pop(1)
        with self.assertRaises(ValueError): self.c.tasks.choose('0x2', 2, 8)
        self.ipc.finish_selection.assert_called_once_with(8, False)
        self.assertEqual(self.ipc.focus, '0x1')

    def test_expired_native_selection_does_not_restore_or_focus(self):
        self.c.command('minimize', target='0x2', pid=2)
        self.ipc.commands.clear()
        self.ipc.check_selection.side_effect = IPCError('expired')
        with self.assertRaises(IPCError): self.c.tasks.choose('0x2', 2, 9)
        self.assertEqual(self.ipc.commands, [])
        self.ipc.finish_selection.assert_called_once_with(9, False)
        self.assertIn('minimized', self.c.windows['0x2'])

    def test_workspace_change_starts_new_cycle(self):
        self.c.command('alt-tab')
        self.ipc.clients.extend([window(4, True, '2'), window(5, True, '2')])
        self.ipc.current = {'id': 2, 'name': '2'}
        self.ipc.focus = '0x4'
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x5')
        self.c.command('alt-tab-commit')
        self.assertEqual(self.ipc.focus, '0x5')

    def test_workspace_change_cancels_old_commit_even_for_pinned_window(self):
        self.ipc.clients[1]['pinned'] = True
        self.c.command('alt-tab')
        self.ipc.current = {'id': 2, 'name': '2'}
        self.assertIsNone(self.c.command('alt-tab-commit')['focused'])
        self.assertEqual(self.ipc.focus, '0x1')

    def test_mru_prunes_closed_windows(self):
        self.c.tasks.focused('0x2')
        self.ipc.clients.pop(1)
        self.c.command('alt-tab')
        self.assertNotIn('0x2', [key[0] for key in self.c.tasks.history])

    def test_cycle_keeps_order_until_alt_release(self):
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x2')
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x3')
        self.assertEqual(self.ipc.focus, '0x1')
        self.c.command('alt-tab-commit')
        self.assertEqual(self.ipc.focus, '0x3')
        self.ipc.raise_window.assert_called_once()

    def test_shift_cycles_backwards(self):
        self.assertEqual(self.c.command('alt-tab', 'reverse')['selected'], '0x3')

    def test_escape_does_not_change_focus(self):
        self.c.command('alt-tab'); self.c.command('alt-tab-cancel')
        self.assertEqual(self.ipc.focus, '0x1')
        self.assertEqual(self.ipc.commands, [])

    def test_mru_after_commit(self):
        self.c.command('alt-tab'); self.c.command('alt-tab-commit')
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x1')

    def test_selected_minimized_restores_only_that_window(self):
        self.c.command('minimize', target='0x2', pid=2)
        self.c.command('minimize', target='0x3', pid=3)
        self.c.tasks.click('0x2', 2)
        self.assertEqual(self.ipc.focus, '0x2')
        self.assertNotIn('minimized', self.c.windows['0x2'])
        self.assertIn('minimized', self.c.windows['0x3'])

    def test_overview_does_not_unminimize_windows(self):
        self.c.command('minimize', target='0x2', pid=2)
        self.ipc.commands.clear()
        result = self.c.command('overview')
        self.assertEqual(result['minimized'], 1)
        self.assertEqual(self.ipc.commands, [])
        self.ipc.toggle_overview.assert_not_called()
        self.assertEqual(self.ipc.present_tasks.call_args.args[0], 3)
        self.assertIn('0x2', [w['address'] for w in self.ipc.present_tasks.call_args.args[1]])

    def test_overview_excludes_other_workspace_but_keeps_pinned(self):
        self.ipc.clients[1]['workspace'] = {'id': 2, 'name': '2'}
        self.ipc.clients[2]['workspace'] = {'id': 2, 'name': '2'}
        self.ipc.clients[2]['pinned'] = True
        self.c.command('overview')
        self.assertEqual({w['address'] for w in self.ipc.present_tasks.call_args.args[1]}, {'0x1', '0x3'})

    def test_overview_uses_minimized_origin_workspace(self):
        self.ipc.clients[1]['workspace'] = {'id': 2, 'name': '2'}
        self.c.command('minimize', target='0x2', pid=2)
        self.c.command('overview')
        self.assertNotIn('0x2', [w['address'] for w in self.ipc.present_tasks.call_args.args[1]])

    def test_closed_selection_not_redirected(self):
        self.c.command('alt-tab')
        self.ipc.clients.pop(1)
        with self.assertRaises(ValueError): self.c.command('alt-tab-commit')
        self.assertEqual(self.ipc.focus, '0x1')

    def test_reused_address_rejected(self):
        self.c.command('alt-tab')
        self.ipc.clients[1]['pid'] = 99
        with self.assertRaises(ValueError): self.c.command('alt-tab-commit')
        self.assertEqual(self.ipc.focus, '0x1')

    def test_other_workspace_excluded_but_pinned_remains_selectable(self):
        self.ipc.clients[1]['workspace'] = {'id': 2, 'name': '2'}
        self.ipc.clients[1]['fullscreen'] = 1
        self.ipc.clients[2]['pinned'] = True
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x3')
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x1')

    def test_current_workspace_fullscreen_is_selectable(self):
        self.ipc.clients[1]['fullscreen'] = 1
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x2')

    def test_alt_tab_excludes_minimized_from_other_workspace(self):
        self.ipc.clients[1]['workspace'] = {'id': 2, 'name': '2'}
        self.c.command('minimize', target='0x2', pid=2)
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x3')

    def test_other_special_workspaces_are_excluded(self):
        self.ipc.clients[1]['workspace'] = {'id': -10, 'name': 'special:other'}
        self.assertEqual(self.c.command('alt-tab')['selected'], '0x3')

class OverviewTests(unittest.TestCase):
    def test_loaded_provider_does_not_install_again(self):
        cmd = Mock()
        overview.ensure(cmd, lambda: [{'name':'Hyprtasking'}])
        cmd.assert_not_called()

    def test_install_checks_loaded_provider(self):
        command = Mock(return_value='')
        plugins = Mock(side_effect=[[], [{'name': 'Hyprtasking'}]])
        with patch('floatland.overview.shutil.which', return_value='/bin/hyprpm'), patch('floatland.overview.interactive') as run:
            run.return_value = 0
            overview.ensure(command, plugins)
        self.assertIn(['hyprpm','add',overview.REPOSITORY], [c.args[0] for c in run.call_args_list])

    def test_failed_install_stops_without_false_success(self):
        with patch('floatland.overview.shutil.which', return_value='/bin/hyprpm'), patch('floatland.overview.interactive') as run:
            run.return_value = 1
            with self.assertRaises(IPCError): overview.ensure(Mock(return_value=''), lambda: [])

    def test_configuration_preserves_previous_values(self):
        ipc = Mock()
        ipc.query.side_effect = [[{'height':1080,'scale':1}], {'str':'grid'}, {'int':0}, {'float':300.0}, {'int':272}, {'int':273}]
        saved = overview.configure(ipc)
        self.assertEqual(saved, {'layout':'grid','linear:top':0,'linear:height':300.0,'drag_button':272,'select_button':273})
        self.assertIn('linear={top=1,height=320.0}', ipc.evaluate.call_args.args[0])
        overview.apply(ipc, saved)
        self.assertIn('layout="grid",linear={top=0,height=300.0}', ipc.evaluate.call_args.args[0])
