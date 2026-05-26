"""Integration tests for devtool.adapters.env_file_store.FilesystemEnvFileStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from devtool.adapters.env_file_store import FilesystemEnvFileStore
from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy


def _svc(
    name: str = "backend",
    env_file: str = ".env",
    directory: str = "backend",
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path(directory),
        type=ServiceType.PYTHON,
        launch="echo ok",
        venv=VenvConfig(strategy=VenvStrategy.NONE),
        env_file=env_file,
        env_entries={"KEY": "val"},
    )


@pytest.fixture
def store(tmp_path: Path) -> FilesystemEnvFileStore:
    (tmp_path / "backend").mkdir()
    return FilesystemEnvFileStore(tmp_path)


class TestExists:
    def test_false_when_no_file(self, store: FilesystemEnvFileStore) -> None:
        assert store.exists(_svc()) is False

    def test_true_when_file_present(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        (tmp_path / "backend" / ".env").write_text("X=1\n")
        assert store.exists(_svc()) is True


class TestReadEntries:
    def test_empty_when_no_file(self, store: FilesystemEnvFileStore) -> None:
        assert store.read_entries(_svc()) == {}

    def test_parses_key_value_pairs(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        (tmp_path / "backend" / ".env").write_text(
            "# comment\n\nKEY=value\nOTHER=123\n"
        )
        entries = store.read_entries(_svc())
        assert entries == {"KEY": "value", "OTHER": "123"}

    def test_skips_comments_and_blank_lines(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        (tmp_path / "backend" / ".env").write_text(
            "# header\n\n  # indented\nA=1\n"
        )
        assert store.read_entries(_svc()) == {"A": "1"}


class TestReadRaw:
    def test_none_when_no_file(self, store: FilesystemEnvFileStore) -> None:
        assert store.read_raw(_svc()) is None

    def test_returns_full_content(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        content = "# header\nKEY=val\n"
        (tmp_path / "backend" / ".env").write_text(content)
        assert store.read_raw(_svc()) == content


class TestWrite:
    def test_creates_file(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        store.write(_svc(), "KEY=val\n")
        assert (tmp_path / "backend" / ".env").read_text() == "KEY=val\n"

    def test_overwrites_existing(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        env_path = tmp_path / "backend" / ".env"
        env_path.write_text("OLD=1\n")
        store.write(_svc(), "NEW=2\n")
        assert env_path.read_text() == "NEW=2\n"


class TestAppendLines:
    def test_appends_to_existing(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        env_path = tmp_path / "backend" / ".env"
        env_path.write_text("A=1\n")
        store.append_lines(_svc(), ["B=2\n", "C=3\n"])
        assert env_path.read_text() == "A=1\nB=2\nC=3\n"


class TestReplaceValue:
    def test_replaces_specific_key(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        env_path = tmp_path / "backend" / ".env"
        env_path.write_text("A=1\nB=old\nC=3\n")
        store.replace_value(_svc(), "B", "new")
        lines = env_path.read_text().splitlines()
        assert lines == ["A=1", "B=new", "C=3"]

    def test_leaves_other_keys_untouched(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        env_path = tmp_path / "backend" / ".env"
        env_path.write_text("X=1\nY=2\nZ=3\n")
        store.replace_value(_svc(), "Y", "updated")
        assert "X=1\n" in env_path.read_text()
        assert "Z=3\n" in env_path.read_text()


class TestSharedSecret:
    def test_read_returns_none_initially(
        self, store: FilesystemEnvFileStore,
    ) -> None:
        assert store.read_shared_secret() is None

    def test_write_then_read(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        store.write_shared_secret("mysecret")
        assert store.read_shared_secret() == "mysecret"

    def test_restrictive_permissions(
        self, store: FilesystemEnvFileStore, tmp_path: Path,
    ) -> None:
        store.write_shared_secret("key123")
        secret_path = tmp_path / "local-development" / ".dev-secret-key"
        mode = secret_path.stat().st_mode & 0o777
        assert mode == 0o600
