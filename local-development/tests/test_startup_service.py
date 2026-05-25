"""Tests for devtool.services.startup_service (start flow, shell, exec)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import (
    InfraComponent,
    ServiceInfo,
    ServiceType,
    VenvConfig,
    VenvStrategy,
    WindowLayout,
)
from devtool.services.startup_service import StartupService


def _make_service(
    name: str,
    *,
    is_primary: bool = True,
    port: int | None = 8000,
    svc_type: ServiceType = ServiceType.PYTHON,
    env_file: str | None = None,
    env_entries: dict[str, str] | None = None,
    directory: str = "test",
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path(directory),
        type=svc_type,
        launch="echo ok",
        venv=VenvConfig(strategy=VenvStrategy.NONE),
        port=port,
        is_primary=is_primary,
        env_file=env_file,
        env_entries=env_entries or {},
    )


def _make_startup_service(
    services: list[ServiceInfo],
    groups: dict[str, list[str]] | None = None,
    *,
    infra: list[InfraComponent] | None = None,
) -> StartupService:
    registry = MagicMock()
    by_name = {s.name: s for s in services}

    registry.get_service.side_effect = lambda n: by_name[n]
    registry.all_services.return_value = services
    registry.primary_services.return_value = [s for s in services if s.is_primary]
    registry.log_dir = Path("/tmp/unifai-dev-test/logs")

    infra_list = infra or []
    infra_by_name = {c.name: c for c in infra_list}
    registry.all_infra.return_value = infra_list
    registry.get_infra.side_effect = lambda n: infra_by_name[n]
    registry.infra_for_services.return_value = infra_list

    def resolve(targets):
        seen: set[str] = set()
        result: list[ServiceInfo] = []
        for t in targets:
            if groups and t in groups:
                for sn in groups[t]:
                    if sn not in seen:
                        seen.add(sn)
                        result.append(by_name[sn])
            else:
                if t not in seen:
                    seen.add(t)
                    result.append(by_name[t])
        return result

    registry.resolve_services.side_effect = resolve

    return StartupService(
        registry=registry,
        root=Path("/fake"),
        container_runtime=MagicMock(),
        session_manager=MagicMock(),
        process_manager=MagicMock(),
        venv_service=MagicMock(),
        env_service=MagicMock(),
    )


class TestValidateStart:
    def test_primary_only_passes(self) -> None:
        services = [_make_service("a"), _make_service("b")]
        StartupService._validate_start(services, fg=False)

    def test_non_primary_alone_rejected(self) -> None:
        services = [_make_service("w", is_primary=False)]
        with pytest.raises(RuntimeError, match="non-primary"):
            StartupService._validate_start(services, fg=False)

    def test_non_primary_with_primary_passes(self) -> None:
        services = [
            _make_service("a"),
            _make_service("w", is_primary=False),
        ]
        StartupService._validate_start(services, fg=False)

    def test_fg_single_primary_passes(self) -> None:
        services = [_make_service("a")]
        StartupService._validate_start(services, fg=True)

    def test_fg_multiple_services_rejected(self) -> None:
        services = [_make_service("a"), _make_service("b")]
        with pytest.raises(RuntimeError, match="exactly one"):
            StartupService._validate_start(services, fg=True)

    def test_fg_non_primary_rejected(self) -> None:
        services = [_make_service("w", is_primary=False)]
        with pytest.raises(RuntimeError, match="non-primary"):
            StartupService._validate_start(services, fg=True)


class TestBuildDefaultLayout:
    def test_primary_only(self) -> None:
        svcs = [_make_service("a"), _make_service("b")]
        layout = StartupService._build_default_layout(svcs)
        assert len(layout) == 1
        assert layout[0].name == "services"
        assert [s.name for s in layout[0].services] == ["a", "b"]

    def test_primary_and_workers(self) -> None:
        svcs = [
            _make_service("a"),
            _make_service("b"),
            _make_service("w1", is_primary=False),
            _make_service("w2", is_primary=False),
        ]
        layout = StartupService._build_default_layout(svcs)
        assert len(layout) == 2
        assert layout[0].name == "services"
        assert [s.name for s in layout[0].services] == ["a", "b"]
        assert layout[1].name == "workers"
        assert [s.name for s in layout[1].services] == ["w1", "w2"]

    def test_workers_only(self) -> None:
        svcs = [_make_service("w", is_primary=False)]
        layout = StartupService._build_default_layout(svcs)
        assert len(layout) == 1
        assert layout[0].name == "workers"

    def test_empty(self) -> None:
        layout = StartupService._build_default_layout([])
        assert layout == []


class TestBuildCustomLayout:
    def test_named_windows(self) -> None:
        svc_a = _make_service("a")
        svc_b = _make_service("b")
        svc_c = _make_service("c")
        ss = _make_startup_service([svc_a, svc_b, svc_c])

        layout = ss._build_custom_layout(
            window_specs=[("win1", ["a", "b"]), ("win2", ["c"])],
            bare_targets=[],
            all_services=[svc_a, svc_b, svc_c],
        )
        assert len(layout) == 2
        assert layout[0].name == "win1"
        assert [s.name for s in layout[0].services] == ["a", "b"]
        assert layout[1].name == "win2"
        assert [s.name for s in layout[1].services] == ["c"]

    def test_auto_named_single_service(self) -> None:
        svc_a = _make_service("a")
        ss = _make_startup_service([svc_a])

        layout = ss._build_custom_layout(
            window_specs=[(None, ["a"])],
            bare_targets=[],
            all_services=[svc_a],
        )
        assert layout[0].name == "a"

    def test_auto_named_multi_service(self) -> None:
        svc_a = _make_service("a")
        svc_b = _make_service("b")
        ss = _make_startup_service([svc_a, svc_b])

        layout = ss._build_custom_layout(
            window_specs=[(None, ["a", "b"])],
            bare_targets=[],
            all_services=[svc_a, svc_b],
        )
        assert layout[0].name == "window-0"

    def test_bare_targets_in_services_window(self) -> None:
        svc_a = _make_service("a")
        svc_b = _make_service("b")
        svc_w = _make_service("w", is_primary=False)
        ss = _make_startup_service([svc_a, svc_b, svc_w])

        layout = ss._build_custom_layout(
            window_specs=[("workers", ["w"])],
            bare_targets=["a", "b"],
            all_services=[svc_a, svc_b, svc_w],
        )
        assert len(layout) == 2
        assert layout[0].name == "services"
        assert [s.name for s in layout[0].services] == ["a", "b"]
        assert layout[1].name == "workers"
        assert [s.name for s in layout[1].services] == ["w"]

    def test_remaining_services_in_other_window(self) -> None:
        svc_a = _make_service("a")
        svc_b = _make_service("b")
        svc_c = _make_service("c")
        ss = _make_startup_service([svc_a, svc_b, svc_c])

        layout = ss._build_custom_layout(
            window_specs=[("mywin", ["a"])],
            bare_targets=[],
            all_services=[svc_a, svc_b, svc_c],
        )
        assert len(layout) == 2
        assert layout[0].name == "mywin"
        assert layout[1].name == "services"
        assert [s.name for s in layout[1].services] == ["b", "c"]

    def test_dedup_across_bare_and_window(self) -> None:
        svc_a = _make_service("a")
        ss = _make_startup_service([svc_a])

        layout = ss._build_custom_layout(
            window_specs=[(None, ["a"])],
            bare_targets=["a"],
            all_services=[svc_a],
        )
        assert len(layout) == 1
        assert layout[0].name == "services"
        assert [s.name for s in layout[0].services] == ["a"]

    def test_group_expansion(self) -> None:
        svc_a = _make_service("a")
        svc_w = _make_service("w", is_primary=False)
        ss = _make_startup_service(
            [svc_a, svc_w],
            groups={"mygroup": ["a", "w"]},
        )

        layout = ss._build_custom_layout(
            window_specs=[("grp", ["mygroup"])],
            bare_targets=[],
            all_services=[svc_a, svc_w],
        )
        assert len(layout) == 1
        assert layout[0].name == "grp"
        assert [s.name for s in layout[0].services] == ["a", "w"]


# ---------------------------------------------------------------------------
# _build_context_command
# ---------------------------------------------------------------------------

class TestBuildContextCommand:
    def test_python_service_includes_activate(self) -> None:
        svc = _make_service("backend", env_file=".env")
        ss = _make_startup_service([svc])
        ctx = ss._build_context_command(svc, "3.12")
        assert "cd" in ctx
        assert "source venv/bin/activate" in ctx

    def test_node_service_skips_activate(self) -> None:
        svc = _make_service("ui", svc_type=ServiceType.NODE, env_file=".env.local")
        ss = _make_startup_service([svc])
        ctx = ss._build_context_command(svc, "3.12")
        assert "source venv/bin/activate" not in ctx
        assert ".env.local" in ctx

    def test_no_env_file(self) -> None:
        svc = _make_service("svc")
        ss = _make_startup_service([svc])
        ctx = ss._build_context_command(svc, "3.12")
        assert "source" in ctx  # venv activate
        assert "set -a" not in ctx


# ---------------------------------------------------------------------------
# shell
# ---------------------------------------------------------------------------

class TestShell:
    @patch("devtool.services.startup_service.resolve_bash", return_value="/usr/bin/bash")
    @patch("os.execvp")
    def test_shell_calls_execvp_with_bash(self, mock_execvp, mock_bash) -> None:
        svc = _make_service("backend", env_file=".env")
        ss = _make_startup_service([svc])
        ss._venv_svc.detect_python = MagicMock(return_value=("/usr/bin/python3.12", "3.12"))

        ss.shell("backend")

        mock_execvp.assert_called_once()
        args = mock_execvp.call_args
        assert args[0][0] == "/usr/bin/bash"
        shell_cmd = args[0][1][2]
        assert "exec bash" in shell_cmd
        assert "source venv/bin/activate" in shell_cmd
        assert "echo ok" not in shell_cmd


# ---------------------------------------------------------------------------
# exec_in_context
# ---------------------------------------------------------------------------

class TestExecInContext:
    @patch("devtool.services.startup_service.resolve_bash", return_value="/usr/bin/bash")
    @patch("devtool.services.startup_service.subprocess.run", return_value=MagicMock(returncode=0))
    def test_exec_runs_user_command(self, mock_run, mock_bash) -> None:
        svc = _make_service("backend")
        ss = _make_startup_service([svc])
        ss._venv_svc.detect_python = MagicMock(return_value=("/usr/bin/python3.12", "3.12"))

        rc = ss.exec_in_context("backend", ["pytest", "-x"])

        mock_run.assert_called_once()
        shell_cmd = mock_run.call_args[0][0][2]
        assert "pytest" in shell_cmd
        assert rc == 0

    @patch("devtool.services.startup_service.resolve_bash", return_value="/usr/bin/bash")
    @patch("devtool.services.startup_service.subprocess.run", return_value=MagicMock(returncode=0))
    def test_exec_single_command(self, mock_run, mock_bash) -> None:
        svc = _make_service("backend")
        ss = _make_startup_service([svc])
        ss._venv_svc.detect_python = MagicMock(return_value=("/usr/bin/python3.12", "3.12"))

        rc = ss.exec_in_context("backend", ["pip", "list"])

        shell_cmd = mock_run.call_args[0][0][2]
        assert "pip" in shell_cmd
        assert rc == 0
