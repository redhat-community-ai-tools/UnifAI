"""Tests for devtool.services.infra_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from devtool.domain.models import ContainerStatus, InfraComponent
from devtool.services.infra_service import InfraService


def _make_comp(name: str, label: str = "") -> InfraComponent:
    return InfraComponent(
        name=name, image=f"{name}:latest",
        ports=[f"1000:1000"], label=label or name.title(),
    )


def _make_service(
    infra: list[InfraComponent] | None = None,
) -> InfraService:
    registry = MagicMock()
    infra = infra or []
    by_name = {c.name: c for c in infra}

    registry.all_infra.return_value = infra
    registry.get_infra.side_effect = lambda n: by_name[n]
    registry.log_dir = Path("/tmp/test-logs")

    runtime = MagicMock()
    runtime.runtime_name = "podman"

    return InfraService(registry=registry, container_runtime=runtime)


class TestStart:
    def test_starts_all_infra(self, tmp_path: Path) -> None:
        comps = [_make_comp("mongo"), _make_comp("redis")]
        svc = _make_service(comps)
        svc._registry.log_dir = tmp_path / "logs"

        svc.start()

        assert svc._runtime.ensure_running.call_count == 2

    def test_starts_specific_targets(self, tmp_path: Path) -> None:
        comps = [_make_comp("mongo"), _make_comp("redis")]
        svc = _make_service(comps)
        svc._registry.log_dir = tmp_path / "logs"

        svc.start(targets=["redis"])

        svc._runtime.ensure_running.assert_called_once()

    def test_for_service_uses_infra_for_services(self, tmp_path: Path) -> None:
        comps = [_make_comp("mongo")]
        svc = _make_service(comps)
        svc._registry.log_dir = tmp_path / "logs"
        svc._registry.infra_for_services.return_value = comps

        svc.start(for_service="backend")

        svc._registry.get_service.assert_called_once_with("backend")
        svc._runtime.ensure_running.assert_called_once()

    def test_for_service_no_infra_needed(self, tmp_path: Path, capsys) -> None:
        svc = _make_service()
        svc._registry.log_dir = tmp_path / "logs"
        svc._registry.infra_for_services.return_value = []

        svc.start(for_service="ui")

        captured = capsys.readouterr()
        assert "no infrastructure" in captured.out.lower()
        svc._runtime.ensure_running.assert_not_called()


class TestStop:
    def test_stops_all(self) -> None:
        comps = [_make_comp("mongo")]
        svc = _make_service(comps)

        svc.stop()

        svc._runtime.stop_all.assert_called_once_with(comps)


class TestLogs:
    def test_delegates_to_runtime(self) -> None:
        comp = _make_comp("redis")
        svc = _make_service([comp])

        svc.logs("redis", follow=True)

        svc._runtime.logs.assert_called_once_with(comp, follow=True)


class TestReset:
    def test_resets_all(self) -> None:
        comps = [_make_comp("mongo"), _make_comp("redis")]
        svc = _make_service(comps)

        svc.reset()

        assert svc._runtime.reset.call_count == 2

    def test_resets_specific(self) -> None:
        comps = [_make_comp("mongo"), _make_comp("redis")]
        svc = _make_service(comps)

        svc.reset(targets=["mongo"])

        svc._runtime.reset.assert_called_once()


class TestStatus:
    def test_prints_all_statuses(self, capsys) -> None:
        comps = [_make_comp("mongo", "MongoDB"), _make_comp("redis", "Redis")]
        svc = _make_service(comps)
        svc._runtime.status.side_effect = [
            ContainerStatus.RUNNING, ContainerStatus.STOPPED,
        ]

        svc.status()

        captured = capsys.readouterr()
        assert "MongoDB" in captured.out
        assert "running" in captured.out
        assert "Redis" in captured.out
        assert "stopped" in captured.out
