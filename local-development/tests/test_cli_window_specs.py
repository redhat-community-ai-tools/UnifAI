"""Tests for CLI --window spec parsing."""

from __future__ import annotations

from devtool.cli import _parse_window_specs


class TestParseWindowSpecs:
    def test_none_returns_none(self) -> None:
        assert _parse_window_specs(None) is None

    def test_empty_list_returns_none(self) -> None:
        assert _parse_window_specs([]) is None

    def test_unnamed_single_service(self) -> None:
        result = _parse_window_specs(["backend"])
        assert result == [(None, ["backend"])]

    def test_unnamed_multiple_services(self) -> None:
        result = _parse_window_specs(["backend,identity"])
        assert result == [(None, ["backend", "identity"])]

    def test_named_window(self) -> None:
        result = _parse_window_specs(["workers=celery-worker,temporal-worker"])
        assert result == [("workers", ["celery-worker", "temporal-worker"])]

    def test_multiple_windows(self) -> None:
        result = _parse_window_specs([
            "main=backend,identity",
            "rag,celery-worker",
            "agents=multi-agent,temporal-worker",
        ])
        assert result == [
            ("main", ["backend", "identity"]),
            (None, ["rag", "celery-worker"]),
            ("agents", ["multi-agent", "temporal-worker"]),
        ]

    def test_whitespace_stripped(self) -> None:
        result = _parse_window_specs(["  win = a , b "])
        assert result == [("win", ["a", "b"])]

    def test_empty_entries_skipped(self) -> None:
        result = _parse_window_specs(["a,,b,"])
        assert result == [(None, ["a", "b"])]
