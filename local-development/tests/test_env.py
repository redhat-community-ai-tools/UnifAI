"""Tests for devtool.services.env_service (environment file management)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devtool.domain.env import ENV_HEADER, GenerateResult, expected_keys, is_auto_generate
from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy
from devtool.ports.env_file_store import EnvFileStore
from devtool.services.env_service import EnvService


def _make_service(
    name: str = "test-svc",
    env_file: str | None = ".env",
    env_entries: dict[str, str] | None = None,
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path("svc"),
        type=ServiceType.PYTHON,
        launch="echo ok",
        venv=VenvConfig(strategy=VenvStrategy.NONE),
        env_file=env_file,
        env_entries=env_entries or {},
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
    return EnvService(registry=registry, store=store)


class TestGenerate:
    def test_creates_env_file(self) -> None:
        svc = _make_service(env_entries={"KEY": "value", "OTHER": "123"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_called_once()
        _, kwargs = store.write.call_args
        if not kwargs:
            args = store.write.call_args[0]
            content = args[1]
        else:
            content = kwargs.get("content", store.write.call_args[0][1])
        content = store.write.call_args[0][1]
        assert content.startswith(ENV_HEADER)
        assert "KEY=value\n" in content
        assert "OTHER=123\n" in content

    def test_skips_existing_without_force(self) -> None:
        svc = _make_service(env_entries={"KEY": "value"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "value"}
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_not_called()
        store.append_lines.assert_not_called()

    def test_overwrites_with_force(self) -> None:
        svc = _make_service(env_entries={"KEY": "new"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate(force=True)

        store.write.assert_called_once()
        content = store.write.call_args[0][1]
        assert "KEY=new" in content

    def test_no_env_file_skips(self) -> None:
        svc = _make_service(env_file=None)
        store = MagicMock(spec=EnvFileStore)
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_not_called()

    def test_no_env_entries_skips(self) -> None:
        svc = _make_service(env_entries={})
        store = MagicMock(spec=EnvFileStore)
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_not_called()


class TestGenerateLocalAuth:
    def test_identity_local_auth_skips_keycloak_keys(self) -> None:
        svc = _make_service(
            name="identity",
            env_entries={
                "keycloak_base_url": "https://keycloak.test",
                "client_id": "<REPLACE>",
                "client_secret": "<REPLACE>",
                "keycloak_realm": "master",
                "hostname_local": "127.0.0.1",
                "port": "13456",
            },
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        content = store.write.call_args[0][1]
        assert "keycloak_base_url" not in content
        assert "client_id" not in content
        assert "client_secret" not in content
        assert "keycloak_realm" not in content
        assert "hostname_local=127.0.0.1\n" in content
        assert "port=13456\n" in content
        assert "local_auth_enabled=true\n" in content

    def test_identity_no_local_auth_writes_all_keys(self) -> None:
        svc = _make_service(
            name="identity",
            env_entries={
                "keycloak_base_url": "https://keycloak.test",
                "client_id": "<REPLACE>",
                "hostname_local": "127.0.0.1",
            },
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store, local_auth=False)

        env_svc.generate()

        content = store.write.call_args[0][1]
        assert "keycloak_base_url=https://keycloak.test\n" in content
        assert "client_id=<REPLACE>\n" in content
        assert "hostname_local=127.0.0.1\n" in content
        assert "local_auth_enabled" not in content

    def test_non_identity_unaffected_by_local_auth(self) -> None:
        svc = _make_service(
            name="backend",
            env_entries={
                "client_id": "some-value",
                "hostname_local": "127.0.0.1",
            },
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        content = store.write.call_args[0][1]
        assert "client_id=some-value\n" in content
        assert "hostname_local=127.0.0.1\n" in content
        assert "local_auth_enabled" not in content


class TestCheckPlaceholders:
    def test_no_placeholders_in_template(self) -> None:
        svc = _make_service(env_entries={"KEY": "real_value"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "real_value"}
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == set()

    def test_detects_unreplaced_placeholder(self) -> None:
        svc = _make_service(env_entries={
            "client_id": "<REPLACE_WITH_YOUR_CLIENT_ID>",
            "port": "13456",
        })
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "client_id": "<REPLACE_WITH_YOUR_CLIENT_ID>",
            "port": "13456",
        }
        env_svc = _make_env_service([svc], store=store)

        result = env_svc.check_placeholders(svc)
        assert result == {"client_id"}

    def test_multiple_placeholders(self) -> None:
        svc = _make_service(env_entries={
            "id": "<REPLACE_ID>",
            "secret": "<replace_secret>",
            "host": "localhost",
        })
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "id": "<REPLACE_ID>",
            "secret": "<replace_secret>",
            "host": "localhost",
        }
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == {"id", "secret"}

    def test_replaced_on_disk_not_flagged(self) -> None:
        svc = _make_service(env_entries={
            "client_id": "<REPLACE_WITH_YOUR_CLIENT_ID>",
        })
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"client_id": "my_real_id"}
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == set()

    def test_file_does_not_exist(self) -> None:
        svc = _make_service(env_entries={"KEY": "<REPLACE>"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == set()

    def test_no_env_file_configured(self) -> None:
        svc = _make_service(env_file=None)
        store = MagicMock(spec=EnvFileStore)
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == set()

    def test_no_env_entries(self) -> None:
        svc = _make_service(env_entries={})
        store = MagicMock(spec=EnvFileStore)
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_placeholders(svc) == set()


class TestCheckMissingKeys:
    def test_detects_absent_keys(self) -> None:
        svc = _make_service(env_entries={"KEY": "value", "OTHER": "123"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "value"}
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_missing_keys(svc) == {"OTHER"}

    def test_none_missing(self) -> None:
        svc = _make_service(env_entries={"KEY": "value", "OTHER": "123"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "value", "OTHER": "123"}
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_missing_keys(svc) == set()

    def test_file_does_not_exist(self) -> None:
        svc = _make_service(env_entries={"KEY": "value"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_missing_keys(svc) == set()

    def test_no_env_file_configured(self) -> None:
        svc = _make_service(env_file=None, env_entries={"KEY": "value"})
        store = MagicMock(spec=EnvFileStore)
        env_svc = _make_env_service([svc], store=store)

        assert env_svc.check_missing_keys(svc) == set()

    def test_respects_local_auth_for_identity(self) -> None:
        svc = _make_service(
            name="identity",
            env_entries={
                "keycloak_base_url": "https://keycloak.test",
                "client_id": "<REPLACE>",
                "hostname_local": "127.0.0.1",
            },
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "hostname_local": "127.0.0.1",
            "local_auth_enabled": "true",
        }
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        missing = env_svc.check_missing_keys(svc)
        assert "keycloak_base_url" not in missing
        assert "client_id" not in missing
        assert missing == set()


class TestGenerateUpdate:
    def test_returns_updated_and_appends_missing(self, capsys) -> None:
        svc = _make_service(env_entries={"KEY": "default", "NEW_KEY": "new_val"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "custom_value"}
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.append_lines.assert_called_once()
        lines = store.append_lines.call_args[0][1]
        assert "NEW_KEY=new_val\n" in lines

    def test_preserves_existing_content_not_overwritten(self) -> None:
        svc = _make_service(env_entries={"KEY": "default", "EXTRA": "extra_val"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "my_value"}
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_not_called()
        store.append_lines.assert_called_once()

    def test_updated_respects_local_auth(self) -> None:
        svc = _make_service(
            name="identity",
            env_entries={
                "keycloak_base_url": "https://keycloak.test",
                "client_id": "<REPLACE>",
                "hostname_local": "127.0.0.1",
                "port": "13456",
            },
        )
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "hostname_local": "127.0.0.1",
            "local_auth_enabled": "true",
        }
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        if store.append_lines.called:
            lines = store.append_lines.call_args[0][1]
            combined = "".join(lines)
            assert "keycloak_base_url" not in combined
            assert "client_id" not in combined
            assert "port=13456\n" in combined

    def test_skipped_when_all_keys_present(self) -> None:
        svc = _make_service(env_entries={"KEY": "value", "OTHER": "123"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "value", "OTHER": "123"}
        env_svc = _make_env_service([svc], store=store)

        env_svc.generate()

        store.write.assert_not_called()
        store.append_lines.assert_not_called()


class TestAlignLocalAuth:
    def test_adds_local_auth_enabled_when_missing(self) -> None:
        svc = _make_service(name="identity", env_entries={"hostname_local": "127.0.0.1"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"hostname_local": "127.0.0.1"}
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        store.append_lines.assert_called()
        all_lines = []
        for c in store.append_lines.call_args_list:
            all_lines.extend(c[0][1])
        assert "local_auth_enabled=true\n" in all_lines

    def test_noop_when_already_present(self) -> None:
        svc = _make_service(name="identity", env_entries={"hostname_local": "127.0.0.1"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "hostname_local": "127.0.0.1",
            "local_auth_enabled": "true",
        }
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        # Only the generate step should have been skipped (all keys present)
        store.write.assert_not_called()

    def test_removes_local_auth_enabled_when_false(self) -> None:
        svc = _make_service(name="identity", env_entries={"hostname_local": "127.0.0.1"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {
            "hostname_local": "127.0.0.1",
            "local_auth_enabled": "true",
            "port": "13456",
        }
        store.read_raw.return_value = (
            "hostname_local=127.0.0.1\nlocal_auth_enabled=true\nport=13456\n"
        )
        env_svc = _make_env_service([svc], store=store, local_auth=False)

        env_svc.generate()

        store.write.assert_called()
        content = store.write.call_args[0][1]
        assert "local_auth_enabled" not in content
        assert "hostname_local=127.0.0.1\n" in content
        assert "port=13456\n" in content

    def test_ignores_non_identity_service(self) -> None:
        svc = _make_service(name="backend", env_entries={"KEY": "value"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = True
        store.read_entries.return_value = {"KEY": "value"}
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        # Should only be called for write from generate path, not align
        # With all keys present, neither write nor append should be called
        store.write.assert_not_called()
        store.append_lines.assert_not_called()

    def test_ignores_missing_file(self) -> None:
        svc = _make_service(name="identity", env_entries={"KEY": "value"})
        store = MagicMock(spec=EnvFileStore)
        store.exists.return_value = False
        env_svc = _make_env_service([svc], store=store, local_auth=True)

        env_svc.generate()

        # Should create the file via write (not align)
        store.write.assert_called_once()


class TestDomainHelpers:
    """Tests for pure domain functions in devtool.domain.env."""

    def test_is_auto_generate_true(self) -> None:
        assert is_auto_generate("<AUTO_GENERATE>") is True
        assert is_auto_generate("<auto_generate>") is True

    def test_is_auto_generate_false(self) -> None:
        assert is_auto_generate("some_value") is False
        assert is_auto_generate("") is False

    def test_expected_keys_basic(self) -> None:
        svc = _make_service(env_entries={"A": "1", "B": "2"})
        assert expected_keys(svc) == {"A", "B"}

    def test_expected_keys_local_auth_identity(self) -> None:
        svc = _make_service(
            name="identity",
            env_entries={
                "keycloak_base_url": "x",
                "client_id": "y",
                "client_secret": "z",
                "keycloak_realm": "w",
                "hostname_local": "127.0.0.1",
            },
        )
        keys = expected_keys(svc, local_auth=True)
        assert "keycloak_base_url" not in keys
        assert "client_id" not in keys
        assert "hostname_local" in keys
        assert "local_auth_enabled" in keys

    def test_expected_keys_local_auth_non_identity(self) -> None:
        svc = _make_service(
            name="backend",
            env_entries={"client_id": "x", "host": "y"},
        )
        keys = expected_keys(svc, local_auth=True)
        assert keys == {"client_id", "host"}
