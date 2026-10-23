import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from floatland import session
from floatland.ipc import IPCError

class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'build').mkdir()
        (self.root/'build/floatland-bars.so').write_bytes(b'fake plugin')
        for target, value in [('ROOT', self.root), ('instance_dir', lambda: self.root),
                              ('load', lambda **kwargs: {'titlebar_height': 0})]:
            p = patch.object(session, target, value); p.start(); self.addCleanup(p.stop)
        for target in ('command', 'plugins', 'stop_previous', 'plugin_operation', 'Hyprland'):
            p = patch.object(session, target); setattr(self, target, p.start()); self.addCleanup(p.stop)
        self.Hyprland.return_value.query.return_value = {'version': '0.56.2'}
        self.plugins.side_effect = [[], [{'name': 'floatland-bars', 'version': session.__version__}]]
        p = patch.object(session, 'run', new_callable=AsyncMock)
        self.run = p.start(); self.addCleanup(p.stop)
        p = patch.object(session, 'RotatingFileHandler'); p.start(); self.addCleanup(p.stop)
        for target in ('basicConfig', 'FileHandler'):
            p = patch.object(logging, target); p.start(); self.addCleanup(p.stop)

    def test_build_load_run_and_unload_same_version(self):
        session.start()
        self.stop_previous.assert_called_once()
        self.run.assert_awaited_once_with(self.root, {'titlebar_height': 0}, unified=True)
        target = self.root/('floatland-bars-'+session.__version__+'.so')
        self.assertEqual(self.plugin_operation.call_args_list[0].args, ('load', target))
        self.assertEqual(self.plugin_operation.call_args_list[-1].args, ('unload', target))
        self.assertEqual(target.read_bytes(), b'fake plugin')

    def test_running_session_reports_action_without_traceback_or_build(self):
        import io
        import fcntl
        with (self.root/'floatland-session.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            output = io.StringIO()
            with patch('sys.stderr', output), patch.object(session.LOG, 'exception') as log:
                self.assertEqual(session.main(), 1)
            self.assertIn('python3 run.py stop', output.getvalue())
            log.assert_not_called()
            self.command.assert_not_called()
            self.stop_previous.assert_not_called()

    def test_build_failure_does_not_stop_working_daemon(self):
        self.command.side_effect = IPCError('build failed')
        with self.assertRaises(IPCError): session.start()
        self.stop_previous.assert_not_called()
        self.plugin_operation.assert_not_called()

    def test_daemon_failure_unloads_plugin(self):
        self.run.side_effect = IPCError('daemon failed')
        with self.assertRaises(IPCError): session.start()
        self.assertEqual(self.plugin_operation.call_args_list[-1].args[0], 'unload')

    def test_previous_hyprbars_restored_after_session(self):
        previous = self.root/'hyprbars.so'; previous.touch()
        self.plugins.side_effect = [[{'name': 'hyprbars'}], [{'name': 'floatland-bars', 'version': session.__version__}]]
        with patch.object(session, 'mapped_plugins', return_value=[str(previous)]):
            session.start()
        self.assertEqual(self.plugin_operation.call_args_list[0].args, ('unload', str(previous)))
        self.assertEqual(self.plugin_operation.call_args_list[-1].args, ('load', str(previous)))

    def test_wrong_plugin_version_aborts_and_unloads(self):
        self.plugins.side_effect = [[], [{'name': 'floatland-bars', 'version': 'old'}]]
        with self.assertRaises(IPCError): session.start()
        self.run.assert_not_awaited()
        self.assertEqual(self.plugin_operation.call_args_list[-1].args[0], 'unload')

    def test_unknown_conflict_path_keeps_existing_session(self):
        self.plugins.side_effect = [[{'name': 'hyprbars'}]]
        with patch.object(session, 'mapped_plugins', return_value=[]):
            with self.assertRaises(IPCError): session.start()
        self.stop_previous.assert_not_called()

class PathsTests(unittest.TestCase):
    def test_maps_paths_with_spaces_and_duplicates(self):
        with patch.dict('os.environ', {'HYPRLAND_INSTANCE_SIGNATURE': 'test'}), \
             patch.object(session, 'command', return_value=json.dumps([{'instance': 'test', 'pid': 123}])), \
             patch.object(Path, 'read_text', return_value='1-2 r-xp 0 00:00 1 /tmp/hyprbars.so\n'
                          '1-2 r-xp 0 00:00 1 /tmp/hyprbars.so\n'
                          '1-2 r-xp 0 00:00 1 /tmp/other.so\n'):
            self.assertEqual(session.mapped_plugins(), ['/tmp/hyprbars.so'])

    def test_plugin_error_text_with_success_exit_is_rejected(self):
        with patch.object(session, 'command', return_value='plugin not loaded'):
            with self.assertRaises(IPCError): session.plugin_operation('unload', '/tmp/x.so')

class StaleSocketTests(unittest.TestCase):
    def test_nested_missing_or_refused_socket_allows_restart(self):
        for error in (FileNotFoundError('gone'), ConnectionRefusedError('stale')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root/'floatland.sock').touch()
                inner = IPCError('exchange'); inner.__cause__ = error
                outer = IPCError('no daemon'); outer.__cause__ = inner
                with patch.object(session, 'daemon_request', side_effect=outer):
                    session.stop_previous(root)

    def test_other_socket_errors_are_not_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'floatland.sock').touch()
            error = IPCError('timeout'); error.__cause__ = TimeoutError()
            with patch.object(session, 'daemon_request', side_effect=error):
                with self.assertRaises(IPCError): session.stop_previous(root)
