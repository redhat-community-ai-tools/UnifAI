"""Port: .env file storage for reading and writing service environment files."""

from __future__ import annotations

from abc import ABC, abstractmethod

from devtool.domain.models import ServiceInfo


class EnvFileStore(ABC):
    """Abstraction for .env file I/O and shared secret persistence."""

    @abstractmethod
    def exists(self, service: ServiceInfo) -> bool:
        """Return True if the service's .env file exists on disk."""

    @abstractmethod
    def read_entries(self, service: ServiceInfo) -> dict[str, str]:
        """Parse the service's .env file and return ``{key: value}`` pairs.

        Skips comments and blank lines.  Returns an empty dict if the
        file does not exist.
        """

    @abstractmethod
    def read_raw(self, service: ServiceInfo) -> str | None:
        """Return the raw text content of the service's .env file.

        Returns ``None`` if the file does not exist.
        """

    @abstractmethod
    def write(self, service: ServiceInfo, content: str) -> None:
        """Overwrite (or create) the service's .env file with *content*."""

    @abstractmethod
    def append_lines(self, service: ServiceInfo, lines: list[str]) -> None:
        """Append *lines* to the service's existing .env file."""

    @abstractmethod
    def replace_value(self, service: ServiceInfo, key: str, new_value: str) -> None:
        """Rewrite a single ``key=...`` line in the service's .env file."""

    @abstractmethod
    def read_shared_secret(self) -> str | None:
        """Read the shared dev secret.  Returns ``None`` if not yet created."""

    @abstractmethod
    def write_shared_secret(self, value: str) -> None:
        """Persist the shared dev secret with restrictive permissions."""
