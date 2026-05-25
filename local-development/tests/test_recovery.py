"""Tests for devtool.services.recovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import (
    ContainerStatus,
    InfraComponent,
    ServiceInfo,
    ServiceHealth,
    ServiceStatus,
    ServiceType,
    VenvConfig,
    VenvStrategy,
)
from devtool.services.recovery import Recovery


def _make_service(
    name: str, *, is_primary: bool = True, port: int | None = 8000,
) -> ServiceInfo:
    return ServiceInfo(
        name=name, directory=name, type=ServiceType.PYTHON,
        launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
        port=port, is_primary=is_primary, env_file=None, env_entries={},
    )


def _make_recovery(
    services: list[ServiceInfo],
    infra: list[InfraComponent] | None = None,
) -> Recovery:
    registry = MagicMock()
    by_name = {s.name: s for s in services}
    registry.get_service.side_effect = lambda n: by_name[n]
    registry.all_services.return_value = services

    infra = infra or []
    registry.infra_for_services.return_value = infra

    runtime = MagicMock()
    session = MagicMock()
    health = MagicMock()

    return Recovery(
        registry=registry, runtime=runtime,
        session=session, health=health,
    )


class TestRestartService:
    def test_restarts_healthy_infra_skipped(self, capsys) -> None:
        comp = InfraComponent(
            name="redis", image="redis:latest",
            ports=["6379:6379"], label="Redis",
        )
        svc = _make_service("api")
        rec = _make_recovery([svc], infra=[comp])
        rec._runtime.status.return_value = ContainerStatus.RUNNING
        rec._session.is_running.return_value = True
        rec._session.restart_service.return_value = True

        rec.restart_service("api")

        rec._runtime.ensure_running.assert_not_called()
        rec._session.restart_service.assert_called_once()

    def test_starts_stopped_infra_first(self, capsys) -> None:
        comp = InfraComponent(
            name="redis", image="redis:latest",
            ports=["6379:6379"], label="Redis",
        )
        svc = _make_service("api")
        rec = _make_recovery([svc], infra=[comp])
        rec._runtime.status.return_value = ContainerStatus.STOPPED
        rec._session.is_running.return_value = True
        rec._session.restart_service.return_value = True

        rec.restart_service("api")

        rec._runtime.ensure_running.assert_called_once_with(comp)
        captured = capsys.readouterr()
        assert "Restarted infra" in captured.out

    def test_no_session_warns(self, capsys) -> None:
        svc = _make_service("api")
        rec = _make_recovery([svc])
        rec._session.is_running.return_value = False

        rec.restart_service("api")

        captured = capsys.readouterr()
        assert "No active session" in captured.out

    def test_pane_not_found_warns(self, capsys) -> None:
        svc = _make_service("api")
        rec = _make_recovery([svc])
        rec._session.is_running.return_value = True
        rec._session.restart_service.return_value = False

        rec.restart_service("api")

        captured = capsys.readouterr()
        assert "Could not find pane" in captured.out


class TestRestartFailed:
    def test_all_healthy_prints_clean(self, capsys) -> None:
        svc = _make_service("api")
        rec = _make_recovery([svc])
        rec._health.check_service.return_value = ServiceHealth(
            "api", ServiceStatus.HEALTHY, 8000,
            port_open=True, http_healthy=True,
        )

        rec.restart_failed()

        captured = capsys.readouterr()
        assert "All services are healthy" in captured.out

    def test_restarts_down_services(self) -> None:
        svc_ok = _make_service("ok")
        svc_bad = _make_service("bad")
        rec = _make_recovery([svc_ok, svc_bad])
        rec._health.check_service.side_effect = [
            ServiceHealth("ok", ServiceStatus.HEALTHY, 8000, port_open=True, http_healthy=True),
            ServiceHealth("bad", ServiceStatus.DOWN, 8001, port_open=False),
        ]
        rec._session.is_running.return_value = True
        rec._session.restart_service.return_value = True

        rec.restart_failed()

        rec._session.restart_service.assert_called_once()

    def test_skips_no_port_services(self) -> None:
        svc = _make_service("worker", port=None)
        rec = _make_recovery([svc])
        rec._health.check_service.return_value = ServiceHealth(
            "worker", ServiceStatus.NO_PORT, None, port_open=False,
        )

        rec.restart_failed()

        rec._session.restart_service.assert_not_called()
