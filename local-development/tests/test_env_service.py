"""Tests for devtool.services.env_service (public API and orchestration)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy
from devtool.ports.env_file_store import EnvFileStore
from devtool.services.env_service import EnvService


def _make_service(name: str = "backend") -> ServiceInfo:
    return ServiceInfo(
        name=name, directory=Path(name), type=ServiceType.PYTHON,
        launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
        env_file=".env", env_entries={"KEY": "val"},
    )


def _make_env_service(
    services: list[ServiceInfo] | None = None,
    *,
    store: EnvFileStore | None = None,
    local_auth: bool = False,
) -> EnvService:
    registry = MagicMock()
    svcs = services or [_make_service()]
    by_name = {s.name: s for s in svcs}
    registry.all_services.return_value = svcs
    registry.get_service.side_effect = lambda n: by_name[n]
    registry.local_auth = local_auth
    if store is None:
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
    return EnvService(registry=registry, store=store)


class TestGenerate:
    def test_generate_prints_summary(self, capsys) -> None:
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        svc = _make_env_service(store=store)

        svc.generate()

        captured = capsys.readouterr()
        assert "Generated" in captured.out

    def test_generate_force_overwrites(self) -> None:
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        svc = _make_env_service(store=store)

        svc.generate(force=True)

        store.write.assert_called_once()

    def test_generate_prints_warnings_for_placeholders(self, capsys) -> None:
        service = ServiceInfo(
            name="api", directory=Path("api"), type=ServiceType.PYTHON,
            launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={"secret": "<REPLACE_ME>"},
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.side_effect = lambda svc: True
        store.read_entries.return_value = {"secret": "<REPLACE_ME>"}
        env_svc = _make_env_service([service], store=store)

        env_svc.generate()

        captured = capsys.readouterr()
        assert "placeholder" in captured.out


class TestShow:
    def test_show_prints_file_content(self, capsys) -> None:
        store = MagicMock(spec=EnvFileStore)
        store.read_raw.return_value = "KEY=value\n"
        svc = _make_env_service(store=store)

        svc.show("backend")

        captured = capsys.readouterr()
        assert "KEY=value" in captured.out

    def test_show_prints_template_when_missing(self, capsys) -> None:
        store = MagicMock(spec=EnvFileStore)
        store.read_raw.return_value = None
        svc = _make_env_service(store=store)

        svc.show("backend")

        captured = capsys.readouterr()
        assert "does not exist" in captured.out
        assert "KEY=val" in captured.out


class TestAutoResolveGeneratedKeys:
    def test_noop_when_no_keys(self) -> None:
        service = ServiceInfo(
            name="api", directory=Path("api"), type=ServiceType.PYTHON,
            launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={"KEY": "val"},
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "val"}
        svc = _make_env_service([service], store=store)

        svc.auto_resolve_generated_keys()

        store.replace_value.assert_not_called()

    def test_resolves_keys(self, capsys) -> None:
        service = ServiceInfo(
            name="backend", directory=Path("backend"), type=ServiceType.PYTHON,
            launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={"SECRET_KEY": "<AUTO_GENERATE>"},
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"SECRET_KEY": "<AUTO_GENERATE>"}
        store.read_shared_secret.return_value = "s3cr3t"
        svc = _make_env_service([service], store=store)

        svc.auto_resolve_generated_keys()

        store.replace_value.assert_called_once_with(service, "SECRET_KEY", "s3cr3t")
        captured = capsys.readouterr()
        assert "SECRET_KEY" in captured.out
        assert "1 service(s)" in captured.out


class TestResolvePlaceholders:
    def test_no_placeholders(self, capsys) -> None:
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "val"}
        svc = _make_env_service(store=store)

        svc.resolve_placeholders(non_interactive=True)

        captured = capsys.readouterr()
        assert "No placeholders" in captured.out

    def test_non_interactive_warns(self, capsys) -> None:
        service = ServiceInfo(
            name="backend", directory=Path("backend"), type=ServiceType.PYTHON,
            launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.NONE),
            env_file=".env", env_entries={"client_id": "<REPLACE_ID>"},
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"client_id": "<REPLACE_ID>"}
        svc = _make_env_service([service], store=store)

        svc.resolve_placeholders(non_interactive=True)

        captured = capsys.readouterr()
        assert "client_id" in captured.out
        assert "placeholder" in captured.out
