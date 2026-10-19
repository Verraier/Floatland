import errno
from pathlib import Path
import unittest
from unittest.mock import patch

from floatland.cli import daemon_request
from floatland.ipc import IPCError


class DaemonConnectionTests(unittest.TestCase):
    def test_missing_or_stale_socket_explains_foreground_lifetime(self):
        for cause in (FileNotFoundError(errno.ENOENT, "missing"),
                      ConnectionRefusedError(errno.ECONNREFUSED, "stale")):
            error = IPCError(str(cause))
            error.__cause__ = cause
            with self.subTest(cause=type(cause).__name__), patch("floatland.cli.exchange", side_effect=error):
                with self.assertRaisesRegex(IPCError, "second terminal") as result:
                    daemon_request(Path("/tmp/test-session"), "toggle")
                self.assertIn("/tmp/test-session/floatland.sock", str(result.exception))

    def test_other_ipc_errors_are_not_misreported_as_stopped_daemon(self):
        error = IPCError("timeout")
        error.__cause__ = TimeoutError()
        with patch("floatland.cli.exchange", side_effect=error):
            with self.assertRaises(IPCError) as result:
                daemon_request(Path("/tmp/test-session"), "status")
            self.assertIs(result.exception, error)
