"""Tests for devtool.services.diagnostic_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy
from devtool.services.diagnostic_service import DiagnosticService


def _make_service(
    name: str = "backend", *, port: int | None = 8000,
    env_file: str | None = ".env",
) -> ServiceInfo:
    return ServiceInfo(
        name=name, directory=Path(name), type=ServiceType.PYTHON,
        launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
        port=port, env_file=env_file, env_entries={},
    )


def _make_diag(
    services: list[ServiceInfo] | None = None,
    root: Path = Path("/fake"),
) -> DiagnosticService:
    registry = MagicMock()
    svcs = services or [_make_service()]
    registry.all_services.return_value = svcs
    registry.log_dir = root / "logs"
    registry.local_auth = True
    registry.has_node_services.return_value = False
    registry.node_min = None

    env_service = MagicMock()
    env_service.env_file_exists.return_value = True
    env_service.check_missing_keys.return_value = set()
    env_service.check_unresolved.return_value = (set(), set())

    return DiagnosticService(
        registry=registry,
        root=root,
        runtime=MagicMock(),
        session=MagicMock(),
        process_manager=MagicMock(),
        health_checker=MagicMock(),
        infra_service=MagicMock(),
        venv_service=MagicMock(),
        env_service=env_service,
        node_resolver=MagicMock(),
    )


class TestStatus:
    def test_delegates_to_health_checker(self) -> None:
        diag = _make_diag()
        diag._health.check_all.return_value = ([], [])
        diag._health.analyze_issues.return_value = []
        diag._session.pane_contents.return_value = {}

        diag.status()

        diag._health.check_all.assert_called_once()


class TestDoctor:
    def test_prints_python_info(self, capsys) -> None:
        diag = _make_diag()
        diag._venv_svc.detect_python.return_value = ("/usr/bin/python3.12", "3.12")
        diag._venv_svc.check.return_value = []
        diag._process.is_port_in_use.return_value = False

        diag.doctor()

        captured = capsys.readouterr()
        assert "Python" in captured.out
        assert "3.12" in captured.out

    def test_handles_python_detection_failure(self, capsys) -> None:
        diag = _make_diag()
        diag._venv_svc.detect_python.side_effect = RuntimeError("not found")
        diag._venv_svc.check.return_value = []
        diag._process.is_port_in_use.return_value = False

        diag.doctor()

        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_checks_env_files(self, tmp_path: Path) -> None:
        svc = _make_service("api", env_file=".env")
        diag = _make_diag([svc], root=tmp_path)
        diag._venv_svc.detect_python.return_value = ("/usr/bin/python3", "3.12")
        diag._venv_svc.check.return_value = []
        diag._process.is_port_in_use.return_value = False

        diag.doctor()

        diag._env_svc.check_missing_keys.assert_called_once()

    def test_reports_missing_env(self, tmp_path: Path, capsys) -> None:
        svc = ServiceInfo(
            name="api", directory=Path("api"), type=ServiceType.PYTHON,
            launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
            port=8000, env_file=".env", env_entries={"KEY": "val"},
        )
        diag = _make_diag([svc], root=tmp_path)
        diag._venv_svc.detect_python.return_value = ("/usr/bin/python3", "3.12")
        diag._venv_svc.check.return_value = []
        diag._process.is_port_in_use.return_value = False
        diag._env_svc.env_file_exists.return_value = False

        diag.doctor()

        captured = capsys.readouterr()
        assert "missing" in captured.out

    def test_checks_port_availability(self, capsys) -> None:
        svc = _make_service("api", port=8005, env_file=None)
        diag = _make_diag([svc])
        diag._venv_svc.detect_python.return_value = ("/usr/bin/python3", "3.12")
        diag._venv_svc.check.return_value = []
        diag._process.is_port_in_use.return_value = True

        diag.doctor()

        captured = capsys.readouterr()
        assert "in use" in captured.out
        assert "8005" in captured.out


class TestLogs:
    def test_prints_not_found(self, tmp_path: Path, capsys) -> None:
        diag = _make_diag(root=tmp_path)
        diag._registry.log_dir = tmp_path / "logs"

        diag.logs("backend")

        captured = capsys.readouterr()
        assert "No log file" in captured.out

    @patch("subprocess.run")
    def test_cat_existing_log(self, mock_run, tmp_path: Path) -> None:
        diag = _make_diag(root=tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "api.log").write_text("some log")
        diag._registry.log_dir = log_dir

        diag.logs("api")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "cat"

    @patch("subprocess.run")
    def test_tail_follow(self, mock_run, tmp_path: Path) -> None:
        diag = _make_diag(root=tmp_path)
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "api.log").write_text("log")
        diag._registry.log_dir = log_dir

        diag.logs("api", follow=True)

        cmd = mock_run.call_args[0][0]
        assert cmd == ["tail", "-f", str(log_dir / "api.log")]
