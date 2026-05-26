"""Tests for devtool.adapters.process (LocalProcessManager)."""

from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from devtool.adapters.process import LocalProcessManager


class TestIsPortInUse:
    def test_open_port_returns_true(self) -> None:
        mgr = LocalProcessManager()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            assert mgr.is_port_in_use(port) is True
        finally:
            srv.close()

    def test_closed_port_returns_false(self) -> None:
        mgr = LocalProcessManager()
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("127.0.0.1", 0))
        port = srv.getsockname()[1]
        srv.close()
        assert mgr.is_port_in_use(port) is False


class TestFindPortOccupants:
    @patch("shutil.which", return_value="/usr/bin/lsof")
    @patch("subprocess.run")
    def test_lsof_parses_pids(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n5678\n")
        mgr = LocalProcessManager()

        with patch.object(mgr, "_read_proc_name", return_value="python"):
            occupants = mgr.find_port_occupants(8000)

        assert len(occupants) == 2
        assert occupants[0].pid == 1234
        assert occupants[1].pid == 5678

    @patch("shutil.which", return_value="/usr/bin/lsof")
    @patch("subprocess.run")
    def test_lsof_no_results(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        mgr = LocalProcessManager()

        with patch("shutil.which", side_effect=["/usr/bin/lsof", None]):
            with patch.object(mgr, "_find_pids_from_proc", side_effect=OSError):
                occupants = mgr.find_port_occupants(8000)

        assert occupants == []

    @patch("shutil.which", side_effect=[None, "/usr/bin/ss"])
    @patch("subprocess.run")
    def test_ss_fallback(self, mock_run, mock_which) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='LISTEN 0 128 *:8000 *:* users:(("python",pid=42,fd=3))\n',
        )
        mgr = LocalProcessManager()

        occupants = mgr.find_port_occupants(8000)

        assert len(occupants) == 1
        assert occupants[0].pid == 42
        assert occupants[0].name == "python"


class TestKillProcesses:
    @patch("os.kill")
    @patch("time.sleep")
    def test_sends_sigterm_then_sigkill(self, mock_sleep, mock_kill) -> None:
        mgr = LocalProcessManager()
        mock_kill.side_effect = [
            None,           # SIGTERM to 100
            None,           # SIGTERM to 200
            None,           # os.kill(100, 0) — still alive
            None,           # SIGKILL to 100
            ProcessLookupError,  # os.kill(200, 0) — already gone
        ]

        mgr.kill_processes([100, 200], graceful_timeout=0)

        import signal
        assert mock_kill.call_count == 5
        mock_kill.assert_any_call(100, signal.SIGTERM)
        mock_kill.assert_any_call(200, signal.SIGTERM)

    @patch("os.kill")
    @patch("time.sleep")
    def test_deduplicates_pids(self, mock_sleep, mock_kill) -> None:
        mgr = LocalProcessManager()
        mock_kill.side_effect = [
            None,           # SIGTERM to 100 (once)
            ProcessLookupError,  # os.kill(100, 0) — gone
        ]

        mgr.kill_processes([100, 100, 100], graceful_timeout=0)

        import signal
        sigterm_calls = [c for c in mock_kill.call_args_list if c[0][1] == signal.SIGTERM]
        assert len(sigterm_calls) == 1


class TestReadProcName:
    @patch("pathlib.Path.read_text", return_value="python3\n")
    def test_reads_from_proc(self, mock_read) -> None:
        name = LocalProcessManager._read_proc_name(12345)
        assert name == "python3"

    @patch("pathlib.Path.read_text", side_effect=OSError)
    @patch("subprocess.run")
    def test_falls_back_to_ps(self, mock_run, mock_read) -> None:
        mock_run.return_value = MagicMock(stdout="gunicorn\n")
        name = LocalProcessManager._read_proc_name(12345)
        assert name == "gunicorn"

    @patch("pathlib.Path.read_text", side_effect=OSError)
    @patch("subprocess.run", side_effect=OSError)
    def test_returns_unknown_on_failure(self, mock_run, mock_read) -> None:
        name = LocalProcessManager._read_proc_name(12345)
        assert name == "unknown"
