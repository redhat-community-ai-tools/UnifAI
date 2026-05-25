"""Tests for devtool.services.orchestrator (facade: attach, clean, delegation)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import (
    ContainerStatus,
    InfraComponent,
    ServiceInfo,
    ServiceType,
    VenvConfig,
    VenvStrategy,
)
from devtool.services.orchestrator import Orchestrator


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


def _make_orchestrator(
    services: list[ServiceInfo],
    groups: dict[str, list[str]] | None = None,
    *,
    infra: list[InfraComponent] | None = None,
):
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

    return Orchestrator(
        registry=registry,
        root=Path("/fake"),
        container_runtime=MagicMock(),
        session_manager=MagicMock(),
        health_checker=MagicMock(),
        startup_service=MagicMock(),
        infra_service=MagicMock(),
        venv_service=MagicMock(),
        env_service=MagicMock(),
        diagnostic_service=MagicMock(),
        init_service=MagicMock(),
    )


# ---------------------------------------------------------------------------
# attach
# ---------------------------------------------------------------------------

class TestAttach:
    def test_attach_no_session(self, capsys) -> None:
        svc = _make_service("backend")
        orch = _make_orchestrator([svc])
        orch._session.is_running.return_value = False

        orch.attach("backend")

        captured = capsys.readouterr()
        assert "No session" in captured.out

    @patch("subprocess.run")
    def test_attach_finds_pane(self, mock_run) -> None:
        svc = _make_service("backend", directory="backend")
        orch = _make_orchestrator([svc])
        orch._session.is_running.return_value = True
        orch._session.pane_contents.return_value = {
            "0.0": "cd /fake/backend && echo ok",
        }
        orch._health.match_panes_to_services.return_value = {"backend": "0.0"}

        orch.attach("backend")

        orch._session.attach.assert_called_once()

    def test_attach_no_pane_found(self, capsys) -> None:
        svc = _make_service("backend", directory="backend")
        orch = _make_orchestrator([svc])
        orch._session.is_running.return_value = True
        orch._session.pane_contents.return_value = {
            "0.0": "something unrelated",
        }
        orch._health.match_panes_to_services.return_value = {}

        orch.attach("backend")

        captured = capsys.readouterr()
        assert "Could not find" in captured.out


# ---------------------------------------------------------------------------
# clean
# ---------------------------------------------------------------------------

class TestClean:
    def test_clean_logs(self, tmp_path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "backend.log").write_text("log data")
        (log_dir / "rag.log").write_text("log data")

        svc = _make_service("backend")
        orch = _make_orchestrator([svc])
        orch._registry.log_dir = log_dir
        orch._runtime.status.return_value = ContainerStatus.RUNNING

        orch.clean(clean_logs=True, clean_containers=False)

        assert list(log_dir.iterdir()) == []

    def test_clean_dry_run_does_not_delete(self, tmp_path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "backend.log").write_text("log data")

        svc = _make_service("backend")
        orch = _make_orchestrator([svc])
        orch._registry.log_dir = log_dir

        orch.clean(dry_run=True, clean_logs=True, clean_containers=False)

        assert (log_dir / "backend.log").exists()

    def test_clean_stopped_containers(self) -> None:
        comp = InfraComponent(
            name="mongo", image="mongo:latest", ports=["27017:27017"], label="MongoDB",
        )
        svc = _make_service("backend")
        orch = _make_orchestrator([svc], infra=[comp])
        orch._registry.log_dir = Path("/tmp/unifai-dev-test/logs")
        orch._runtime.status.return_value = ContainerStatus.STOPPED

        orch.clean(clean_logs=False, clean_containers=True)

        orch._runtime.remove.assert_called_once_with(comp)

    def test_clean_skips_running_containers(self) -> None:
        comp = InfraComponent(
            name="mongo", image="mongo:latest", ports=["27017:27017"], label="MongoDB",
        )
        svc = _make_service("backend")
        orch = _make_orchestrator([svc], infra=[comp])
        orch._registry.log_dir = Path("/tmp/unifai-dev-test/logs")
        orch._runtime.status.return_value = ContainerStatus.RUNNING

        orch.clean(clean_logs=False, clean_containers=True)

        orch._runtime.remove.assert_not_called()


# ---------------------------------------------------------------------------
# replace_value (tests FilesystemEnvFileStore.replace_value)
# ---------------------------------------------------------------------------

from devtool.adapters.env_file_store import FilesystemEnvFileStore
from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy

def _make_svc_for_env(tmp_path):
    return ServiceInfo(
        name="test", directory=tmp_path.relative_to(tmp_path.parent),
        type=ServiceType.PYTHON, launch="echo ok",
        venv=VenvConfig(strategy=VenvStrategy.NONE),
        env_file=".env", env_entries={},
    )

class TestReplacePlaceholder:
    def test_replaces_placeholder_value(self, tmp_path) -> None:
        env_file = tmp_path / "svc" / ".env"
        env_file.parent.mkdir(parents=True)
        env_file.write_text("key1=value1\nclient_id=<REPLACE>\nkey2=value2\n")
        svc = ServiceInfo(
            name="test", directory=Path("svc"),
            type=ServiceType.PYTHON, launch="echo ok",
            venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={},
        )
        store = FilesystemEnvFileStore(tmp_path)

        store.replace_value(svc, "client_id", "my-secret")

        content = env_file.read_text()
        assert "client_id=my-secret" in content
        assert "key1=value1" in content
        assert "key2=value2" in content
        assert "<REPLACE>" not in content

    def test_leaves_other_keys_untouched(self, tmp_path) -> None:
        env_file = tmp_path / "svc" / ".env"
        env_file.parent.mkdir(parents=True)
        env_file.write_text("a=1\nb=2\nc=3\n")
        svc = ServiceInfo(
            name="test", directory=Path("svc"),
            type=ServiceType.PYTHON, launch="echo ok",
            venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={},
        )
        store = FilesystemEnvFileStore(tmp_path)

        store.replace_value(svc, "b", "new")

        lines = env_file.read_text().splitlines()
        assert lines == ["a=1", "b=new", "c=3"]
