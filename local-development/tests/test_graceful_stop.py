"""Tests for graceful shutdown in TmuxSessionManager and Orchestrator.destroy."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy


class TestTmuxGracefulStop:
    @patch("devtool.adapters.tmux.time.sleep")
    @patch("devtool.adapters.tmux.subprocess.run")
    def test_sends_ctrl_c_to_all_panes(
        self, mock_run: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        from devtool.adapters.tmux import TmuxSessionManager

        mgr = TmuxSessionManager()
        mock_run.side_effect = [
            MagicMock(returncode=0),  # has-session (is_running)
            MagicMock(returncode=0, stdout="%0\n%1\n"),  # list-panes
            MagicMock(),  # send-keys C-c pane %0
            MagicMock(),  # send-keys C-c pane %1
            MagicMock(returncode=1),  # has-session → not running (exited)
        ]

        mgr.graceful_stop("unifai-dev", timeout=5)

        send_keys_calls = [
            c for c in mock_run.call_args_list
            if c.args and "send-keys" in c.args[0]
        ]
        assert len(send_keys_calls) == 2

    @patch("devtool.adapters.tmux.time.sleep")
    @patch("devtool.adapters.tmux.subprocess.run")
    def test_kills_session_after_timeout(
        self, mock_run: MagicMock, mock_sleep: MagicMock,
    ) -> None:
        from devtool.adapters.tmux import TmuxSessionManager

        mgr = TmuxSessionManager()

        call_count = [0]
        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            if cmd[:2] == ["tmux", "has-session"]:
                result.returncode = 0  # always running
            elif cmd[:3] == ["tmux", "list-panes"]:
                result.returncode = 0
                result.stdout = "%0\n"
            elif cmd[:3] == ["tmux", "kill-session"]:
                result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_run.side_effect = side_effect

        import devtool.adapters.tmux as tmux_mod
        original_monotonic = tmux_mod.time.monotonic
        timestamps = iter([0.0, 0.0, 0.0, 0.0, 100.0])
        tmux_mod.time.monotonic = lambda: next(timestamps, 100.0)

        try:
            mgr.graceful_stop("unifai-dev", timeout=5)
        finally:
            tmux_mod.time.monotonic = original_monotonic

        kill_calls = [
            c for c in mock_run.call_args_list
            if c.args and "kill-session" in c.args[0]
        ]
        assert len(kill_calls) >= 1

    @patch("devtool.adapters.tmux.subprocess.run")
    def test_noop_when_session_not_running(
        self, mock_run: MagicMock,
    ) -> None:
        from devtool.adapters.tmux import TmuxSessionManager

        mgr = TmuxSessionManager()
        mock_run.return_value = MagicMock(returncode=1)  # has-session → not running

        mgr.graceful_stop("unifai-dev")

        assert mock_run.call_count == 1


class TestForegroundGracefulStop:
    def test_graceful_stop_is_noop(self) -> None:
        from devtool.adapters.foreground import ForegroundSessionManager

        mgr = ForegroundSessionManager()
        mgr.graceful_stop("unifai-dev")
