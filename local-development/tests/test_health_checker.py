"""Tests for devtool.services.health_checker."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.adapters.health_probe import NetworkHealthProbe
from devtool.adapters.registry_loader import YamlRegistryLoader
from devtool.domain.models import (
    ContainerStatus,
    InfraComponent,
    InfraHealth,
    ServiceInfo,
    ServiceHealth,
    ServiceStatus,
    ServiceType,
    StatusIssue,
    VenvConfig,
    VenvStrategy,
)
from devtool.services.diagnostic_service import DiagnosticService
from devtool.services.health_checker import HealthChecker
from devtool.services.pane_matcher import match_panes_to_services


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_service(
    name: str,
    *,
    port: int | None = 8000,
    host: str = "127.0.0.1",
    health_endpoint: str | None = "/",
    infrastructure: list[str] | None = None,
    is_primary: bool = True,
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path(name),
        type=ServiceType.PYTHON,
        launch="echo ok",
        venv=VenvConfig(strategy=VenvStrategy.NONE),
        port=port,
        host=host,
        health_endpoint=health_endpoint,
        infrastructure=infrastructure or [],
        is_primary=is_primary,
    )


@pytest.fixture()
def yaml_path(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        python:
          min: "3.11"
          max: "3.13"

        infrastructure:
          mongo:
            image: "mongo:latest"
            ports: ["27017:27017"]
            label: "MongoDB"
          redis:
            image: "redis:latest"
            ports: ["6379:6379"]
            label: "Redis"

        services:
          backend:
            directory: "backend"
            port: 8005
            host: "0.0.0.0"
            type: python
            health_endpoint: "/"
            infrastructure: [mongo]
            venv:
              strategy: "requirements"
            launch: "python -m run.dev"

          worker:
            directory: "backend"
            type: python
            is_primary: false
            infrastructure: [mongo, redis]
            venv:
              strategy: "none"
            launch: "celery worker"

          api:
            directory: "api"
            port: 8002
            type: python
            health_endpoint: "/"
            infrastructure: [mongo, redis]
            venv:
              strategy: "none"
            launch: "python -m api"

        groups:
          all: [backend, worker, api]

        logging:
          directory: "/tmp/test-logs"
    """)
    p = tmp_path / "services.yaml"
    p.write_text(content)
    return p


@pytest.fixture()
def mock_probe() -> MagicMock:
    """A mock HealthProbe for injecting into HealthChecker."""
    return MagicMock(spec=NetworkHealthProbe)


# ---------------------------------------------------------------------------
# NetworkHealthProbe (adapter)
# ---------------------------------------------------------------------------

class TestNetworkHealthProbeCheckPort:
    def test_open_port(self) -> None:
        with patch("devtool.adapters.health_probe.socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = MagicMock()
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            probe = NetworkHealthProbe()
            is_open, ms = probe.check_port("127.0.0.1", 8000)
            assert is_open is True
            assert ms is not None

    def test_closed_port(self) -> None:
        with patch("devtool.adapters.health_probe.socket.create_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError
            probe = NetworkHealthProbe()
            is_open, ms = probe.check_port("127.0.0.1", 8000)
            assert is_open is False
            assert ms is None

    def test_timeout(self) -> None:
        with patch("devtool.adapters.health_probe.socket.create_connection") as mock_conn:
            mock_conn.side_effect = TimeoutError
            probe = NetworkHealthProbe()
            is_open, ms = probe.check_port("127.0.0.1", 8000)
            assert is_open is False
            assert ms is None


class TestNetworkHealthProbeCheckHttp:
    def test_healthy_endpoint(self) -> None:
        with patch("devtool.adapters.health_probe.urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = MagicMock()
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            probe = NetworkHealthProbe()
            ok, ms = probe.check_http("127.0.0.1", 8000, "/")
            assert ok is True
            assert ms is not None

    def test_unreachable_endpoint(self) -> None:
        with patch("devtool.adapters.health_probe.urllib.request.urlopen") as mock_open:
            mock_open.side_effect = OSError("Connection refused")
            probe = NetworkHealthProbe()
            ok, ms = probe.check_http("127.0.0.1", 8000, "/")
            assert ok is False
            assert ms is None


# ---------------------------------------------------------------------------
# HealthChecker.check_service (via mock probe)
# ---------------------------------------------------------------------------

class TestCheckService:
    def test_no_port(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        health = checker.check_service(reg, "worker")
        assert health.status is ServiceStatus.NO_PORT
        assert health.port is None
        assert health.port_open is False
        mock_probe.check_port.assert_not_called()

    def test_healthy_with_http(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        mock_probe.check_port.return_value = (True, 3.1)
        mock_probe.check_http.return_value = (True, 5.2)
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        health = checker.check_service(reg, "backend")
        assert health.status is ServiceStatus.HEALTHY
        assert health.port == 8005
        assert health.port_open is True
        assert health.http_healthy is True
        assert health.response_time_ms == 5.2

    def test_port_down(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        mock_probe.check_port.return_value = (False, None)
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        health = checker.check_service(reg, "backend")
        assert health.status is ServiceStatus.DOWN
        assert health.port_open is False

    def test_port_open_but_http_fails(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        mock_probe.check_port.return_value = (True, 3.0)
        mock_probe.check_http.return_value = (False, None)
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        health = checker.check_service(reg, "backend")
        assert health.status is ServiceStatus.UNHEALTHY
        assert health.port_open is True
        assert health.http_healthy is False


# ---------------------------------------------------------------------------
# _check_infra (via HealthChecker.build_dashboard internals)
# ---------------------------------------------------------------------------

class TestCheckInfra:
    def test_running_with_uptime(self, mock_probe: MagicMock) -> None:
        comp = InfraComponent(
            name="mongo", image="mongo:latest",
            ports=["27017:27017"], label="MongoDB",
        )
        runtime = MagicMock()
        runtime.status.return_value = ContainerStatus.RUNNING
        runtime.container_uptime.return_value = "2h 15m"

        checker = HealthChecker(mock_probe)
        result = checker.check_infra(comp, runtime)
        assert result.status is ContainerStatus.RUNNING
        assert result.uptime == "2h 15m"
        assert result.port == 27017

    def test_stopped(self, mock_probe: MagicMock) -> None:
        comp = InfraComponent(
            name="redis", image="redis:latest",
            ports=["6379:6379"], label="Redis",
        )
        runtime = MagicMock()
        runtime.status.return_value = ContainerStatus.STOPPED

        checker = HealthChecker(mock_probe)
        result = checker.check_infra(comp, runtime)
        assert result.status is ContainerStatus.STOPPED
        assert result.uptime is None

    def test_not_created(self, mock_probe: MagicMock) -> None:
        comp = InfraComponent(
            name="redis", image="redis:latest",
            ports=["6379:6379"], label="Redis",
        )
        runtime = MagicMock()
        runtime.status.return_value = ContainerStatus.NOT_CREATED

        checker = HealthChecker(mock_probe)
        result = checker.check_infra(comp, runtime)
        assert result.status is ContainerStatus.NOT_CREATED


# ---------------------------------------------------------------------------
# _analyze_issues
# ---------------------------------------------------------------------------

class TestAnalyzeIssues:
    def test_stopped_infra_identifies_affected_services(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        infra_results = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "1h"),
            InfraHealth("redis", "Redis", 6379, ContainerStatus.STOPPED),
        ]
        service_results = [
            ServiceHealth("backend", ServiceStatus.HEALTHY, 8005, port_open=True, http_healthy=True),
            ServiceHealth("worker", ServiceStatus.NO_PORT, None, port_open=False),
            ServiceHealth("api", ServiceStatus.DOWN, 8002, port_open=False),
        ]

        issues = checker.analyze_issues(reg, infra_results, service_results)
        assert len(issues) == 1
        assert "Redis" in issues[0].description
        assert "worker" in issues[0].affected
        assert "api" in issues[0].affected
        assert "infra start redis" in issues[0].fix

    def test_service_down_without_infra_cause(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        infra_results = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "1h"),
            InfraHealth("redis", "Redis", 6379, ContainerStatus.RUNNING, "1h"),
        ]
        service_results = [
            ServiceHealth("backend", ServiceStatus.DOWN, 8005, port_open=False),
            ServiceHealth("worker", ServiceStatus.NO_PORT, None, port_open=False),
            ServiceHealth("api", ServiceStatus.HEALTHY, 8002, port_open=True, http_healthy=True),
        ]

        issues = checker.analyze_issues(reg, infra_results, service_results)
        assert len(issues) == 1
        assert "backend" in issues[0].description
        assert "restart backend" in issues[0].fix

    def test_no_issues_when_all_healthy(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        infra_results = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "1h"),
            InfraHealth("redis", "Redis", 6379, ContainerStatus.RUNNING, "1h"),
        ]
        service_results = [
            ServiceHealth("backend", ServiceStatus.HEALTHY, 8005, port_open=True, http_healthy=True),
            ServiceHealth("worker", ServiceStatus.NO_PORT, None, port_open=False),
            ServiceHealth("api", ServiceStatus.HEALTHY, 8002, port_open=True, http_healthy=True),
        ]

        issues = checker.analyze_issues(reg, infra_results, service_results)
        assert issues == []

    def test_infra_caused_service_not_duplicated(self, yaml_path: Path, mock_probe: MagicMock) -> None:
        """A service affected by stopped infra should not also appear
        as an independent 'not responding' issue."""
        reg = YamlRegistryLoader.load(yaml_path)
        checker = HealthChecker(mock_probe)
        infra_results = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "1h"),
            InfraHealth("redis", "Redis", 6379, ContainerStatus.STOPPED),
        ]
        service_results = [
            ServiceHealth("backend", ServiceStatus.HEALTHY, 8005, port_open=True, http_healthy=True),
            ServiceHealth("worker", ServiceStatus.NO_PORT, None, port_open=False),
            ServiceHealth("api", ServiceStatus.DOWN, 8002, port_open=False),
        ]

        issues = checker.analyze_issues(reg, infra_results, service_results)
        descriptions = " ".join(i.description for i in issues)
        assert descriptions.count("api") == 1


# ---------------------------------------------------------------------------
# _match_panes_to_services
# ---------------------------------------------------------------------------

class TestMatchPanesToServices:
    def test_matches_by_directory(self) -> None:
        services = [
            _make_service("backend"),
            _make_service("rag"),
        ]
        pane_contents = {
            "0.0": "cd /home/user/backend && source venv/bin/activate",
            "0.1": "cd /home/user/rag && python -m bootstrap",
        }
        result = match_panes_to_services(services, pane_contents)
        assert result == {"backend": "0.0", "rag": "0.1"}

    def test_matches_by_service_name(self) -> None:
        services = [_make_service("multi-agent", infrastructure=["mongo"])]
        pane_contents = {
            "0.0": "starting multi-agent service...",
        }
        result = match_panes_to_services(services, pane_contents)
        assert result == {"multi-agent": "0.0"}

    def test_no_match_returns_empty(self) -> None:
        services = [_make_service("backend")]
        pane_contents = {
            "0.0": "some unrelated output",
        }
        result = match_panes_to_services(services, pane_contents)
        assert result == {}

    def test_empty_panes(self) -> None:
        services = [_make_service("backend")]
        result = match_panes_to_services(services, {})
        assert result == {}

    def test_pane_not_reused(self) -> None:
        """Each pane should be matched to at most one service."""
        svc_a = _make_service("backend")
        svc_b = ServiceInfo(
            name="worker",
            directory=Path("backend"),
            type=ServiceType.PYTHON,
            launch="celery worker",
            venv=VenvConfig(strategy=VenvStrategy.NONE),
            is_primary=False,
        )
        pane_contents = {
            "0.0": "cd /home/user/backend && python -m run.dev",
            "1.0": "cd /home/user/backend && celery worker",
        }
        result = match_panes_to_services([svc_a, svc_b], pane_contents)
        assert len(result) == 2
        assert result["backend"] != result["worker"]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestResolveHost:
    def test_none_defaults_to_localhost(self) -> None:
        svc = ServiceInfo(
            name="x", directory=Path("x"), type=ServiceType.PYTHON,
            launch="echo", venv=VenvConfig(strategy=VenvStrategy.NONE),
            port=8000, host=None,
        )
        assert HealthChecker._resolve_host(svc) == "127.0.0.1"

    def test_zero_addr_maps_to_localhost(self) -> None:
        svc = _make_service("x", host="0.0.0.0")
        assert HealthChecker._resolve_host(svc) == "127.0.0.1"

    def test_explicit_host_preserved(self) -> None:
        svc = _make_service("x", host="192.168.1.1")
        assert HealthChecker._resolve_host(svc) == "192.168.1.1"


class TestParseHostPort:
    def test_standard_mapping(self) -> None:
        assert HealthChecker._parse_host_port("27017:27017") == 27017

    def test_different_host_port(self) -> None:
        assert HealthChecker._parse_host_port("5432:5432") == 5432

    def test_invalid_returns_none(self) -> None:
        assert HealthChecker._parse_host_port("invalid") is None


# ---------------------------------------------------------------------------
# _render_dashboard (smoke test — just verify it doesn't crash)
# ---------------------------------------------------------------------------

class TestRenderDashboard:
    def test_renders_without_error(self, capsys) -> None:
        infra = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "2h 15m"),
            InfraHealth("redis", "Redis", 6379, ContainerStatus.STOPPED),
        ]
        services = [
            ServiceHealth(
                "backend", ServiceStatus.HEALTHY, 8005,
                port_open=True, http_healthy=True,
                response_time_ms=4.2, tmux_pane="tmux:0.0",
            ),
            ServiceHealth("worker", ServiceStatus.NO_PORT, None, port_open=False, tmux_pane="tmux:1.0"),
            ServiceHealth("api", ServiceStatus.DOWN, 8002, port_open=False),
        ]
        issues = [
            StatusIssue("Redis stopped → api affected", "unifai-dev infra start redis", ["api"]),
        ]

        DiagnosticService._render_dashboard(infra, services, issues)

        captured = capsys.readouterr()
        assert "INFRASTRUCTURE" in captured.out
        assert "SERVICES" in captured.out
        assert "ISSUES" in captured.out
        assert "MongoDB" in captured.out
        assert "Redis" in captured.out
        assert "backend" in captured.out
        assert "STOPPED" in captured.out
        assert "healthy" in captured.out
        assert "DOWN" in captured.out

    def test_no_issues_section_when_clean(self, capsys) -> None:
        infra = [
            InfraHealth("mongo", "MongoDB", 27017, ContainerStatus.RUNNING, "1h"),
        ]
        services = [
            ServiceHealth("backend", ServiceStatus.HEALTHY, 8005, port_open=True, http_healthy=True),
        ]

        DiagnosticService._render_dashboard(infra, services, [])

        captured = capsys.readouterr()
        assert "ISSUES" not in captured.out
