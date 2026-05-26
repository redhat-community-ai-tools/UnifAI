"""Adapter: filesystem-backed .env file store."""

from __future__ import annotations

import os
from pathlib import Path

from devtool.domain.models import ServiceInfo
from devtool.ports.env_file_store import EnvFileStore

_SECRET_KEY_FILE = "local-development/.dev-secret-key"


class FilesystemEnvFileStore(EnvFileStore):
    """Reads and writes .env files on the local filesystem."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _env_path(self, service: ServiceInfo) -> Path:
        return self._root / service.directory / service.env_file

    def exists(self, service: ServiceInfo) -> bool:
        return self._env_path(service).exists()

    def read_entries(self, service: ServiceInfo) -> dict[str, str]:
        env_path = self._env_path(service)
        if not env_path.exists():
            return {}
        entries: dict[str, str] = {}
        with open(env_path) as f:
            for line in f:
                stripped = line.lstrip()
                if not stripped or stripped[0] == "#":
                    continue
                eq = stripped.find("=")
                if eq == -1:
                    continue
                entries[stripped[:eq].rstrip()] = stripped[eq + 1:].rstrip("\n")
        return entries

    def read_raw(self, service: ServiceInfo) -> str | None:
        env_path = self._env_path(service)
        if not env_path.exists():
            return None
        return env_path.read_text()

    def write(self, service: ServiceInfo, content: str) -> None:
        self._env_path(service).write_text(content)

    def append_lines(self, service: ServiceInfo, lines: list[str]) -> None:
        with open(self._env_path(service), "a") as f:
            f.writelines(lines)

    def replace_value(self, service: ServiceInfo, key: str, new_value: str) -> None:
        env_path = self._env_path(service)
        lines = env_path.read_text().splitlines(keepends=True)
        with open(env_path, "w") as f:
            for line in lines:
                stripped = line.lstrip()
                if stripped.startswith(f"{key}="):
                    f.write(f"{key}={new_value}\n")
                else:
                    f.write(line)

    def read_shared_secret(self) -> str | None:
        secret_path = self._root / _SECRET_KEY_FILE
        if not secret_path.exists():
            return None
        value = secret_path.read_text().strip()
        return value or None

    def write_shared_secret(self, value: str) -> None:
        secret_path = self._root / _SECRET_KEY_FILE
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(secret_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(value + "\n")
