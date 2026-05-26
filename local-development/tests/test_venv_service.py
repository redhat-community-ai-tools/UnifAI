"""Tests for devtool.services.venv_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy
from devtool.services.venv_service import VenvService


def _make_service(
    name: str = "backend",
    *,
    svc_type: ServiceType = ServiceType.PYTHON,
    strategy: VenvStrategy = VenvStrategy.TOML,
    is_primary: bool = True,
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path(name),
        type=svc_type,
        launch="echo ok",
        venv=VenvConfig(strategy=strategy),
        is_primary=is_primary,
        env_file=None,
        env_entries={},
    )


def _make_venv_service(
    services: list[ServiceInfo] | None = None,
) -> VenvService:
    registry = MagicMock()
    services = services or [_make_service()]
    by_name = {s.name: s for s in services}

    registry.get_service.side_effect = lambda n: by_name[n]
    registry.all_services.return_value = services
    registry.primary_services.return_value = [s for s in services if s.is_primary]
    registry.python_bounds.return_value = ((3, 11), (3, 13))
    registry.log_dir = Path("/tmp/unifai-dev-test/logs")

    venv_manager = MagicMock()
    python_resolver = MagicMock()
    python_resolver.find_python.return_value = ("/usr/bin/python3.12", "3.12")

    return VenvService(
        registry=registry,
        root=Path("/fake"),
        venv_manager=venv_manager,
        python_resolver=python_resolver,
    )


class TestDetectPython:
    def test_delegates_to_resolver(self) -> None:
        vs = _make_venv_service()
        path, minor = vs.detect_python()

        assert path == "/usr/bin/python3.12"
        assert minor == "3.12"
        vs._python_resolver.find_python.assert_called_once_with(
            (3, 11), (3, 13), env_override=None,
        )

    @patch.dict("os.environ", {"UNIFAI_PYTHON": "/custom/python3"})
    def test_env_override_passed(self) -> None:
        vs = _make_venv_service()
        vs.detect_python()

        vs._python_resolver.find_python.assert_called_once_with(
            (3, 11), (3, 13), env_override="/custom/python3",
        )


class TestCheck:
    def test_returns_empty_on_success(self) -> None:
        svcs = [_make_service("a"), _make_service("b")]
        vs = _make_venv_service(svcs)

        errors = vs.check()
        assert errors == []

    def test_returns_failed_names(self) -> None:
        svcs = [_make_service("a"), _make_service("b")]
        vs = _make_venv_service(svcs)
        vs._venv.verify.side_effect = [None, RuntimeError("mismatch")]

        errors = vs.check()
        assert errors == ["b"]

    def test_filters_python_services_only(self) -> None:
        svcs = [
            _make_service("api"),
            _make_service("ui", svc_type=ServiceType.NODE),
        ]
        vs = _make_venv_service(svcs)

        vs.check()

        vs._venv.verify.assert_called_once()
        call_svc = vs._venv.verify.call_args[0][0]
        assert call_svc.name == "api"


class TestSetup:
    def test_creates_venvs(self, tmp_path: Path) -> None:
        svcs = [_make_service("svc1")]
        vs = _make_venv_service(svcs)
        vs._registry.log_dir = tmp_path / "logs"
        vs._venv.exists.return_value = False

        vs.setup()

        vs._venv.create.assert_called_once()

    def test_setup_single_service(self) -> None:
        svcs = [_make_service("a"), _make_service("b")]
        vs = _make_venv_service(svcs)
        vs._registry.log_dir = Path("/tmp/test-logs")

        vs.setup("a")

        vs._venv.create.assert_called_once()
        call_svc = vs._venv.create.call_args[0][0]
        assert call_svc.name == "a"


class TestSync:
    def test_syncs_existing(self, tmp_path: Path) -> None:
        svcs = [_make_service("svc1")]
        vs = _make_venv_service(svcs)
        vs._registry.log_dir = tmp_path / "logs"

        vs.sync()

        vs._venv.sync.assert_called_once()


class TestExistingVenvs:
    def test_filters_existing(self) -> None:
        svcs = [_make_service("a"), _make_service("b"), _make_service("c")]
        vs = _make_venv_service(svcs)
        vs._venv.exists.side_effect = [True, False, True]

        result = vs.existing_venvs(svcs)

        assert [s.name for s in result] == ["a", "c"]


class TestRunBatch:
    def test_collects_errors(self, capsys) -> None:
        svcs = [_make_service("ok"), _make_service("fail")]
        vs = _make_venv_service(svcs)

        def action(svc):
            if svc.name == "fail":
                raise RuntimeError("boom")
            return None

        errors = vs._run_batch(svcs, action, fail_label="Failed for")
        assert errors == ["fail"]

        captured = capsys.readouterr()
        assert "ok" in captured.out
        assert "boom" in captured.out
        assert "Failed for" in captured.out

    def test_custom_message(self, capsys) -> None:
        svcs = [_make_service("svc")]
        vs = _make_venv_service(svcs)

        vs._run_batch(svcs, lambda s: "custom msg", fail_label="Err")

        captured = capsys.readouterr()
        assert "custom msg" in captured.out
