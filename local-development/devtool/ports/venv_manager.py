"""Port: virtual-environment manager."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from devtool.domain.models import ServiceInfo


class VenvManager(ABC):

    @abstractmethod
    def create(
        self, service: ServiceInfo, python: str, root: Path,
        *, log_dir: Path | None = None, force: bool = False,
    ) -> None:
        """Create and populate a virtual environment for the service.

        When *log_dir* is given, verbose install output is redirected to
        ``{log_dir}/{service.name}.log`` instead of printing to stdout.

        When *force* is True, an existing venv is deleted and recreated.
        When False, an existing venv is left as-is (the call is a no-op).
        """

    @abstractmethod
    def verify(self, service: ServiceInfo, python_minor: str, root: Path) -> None:
        """Verify the venv exists and its Python matches *python_minor*.

        Raises RuntimeError on mismatch or missing venv.
        """

    @abstractmethod
    def exists(self, service: ServiceInfo, root: Path) -> bool:
        """Return True if the venv directory already exists."""

    @abstractmethod
    def sync(
        self, service: ServiceInfo, python: str, root: Path,
        *, log_dir: Path | None = None,
    ) -> None:
        """Update dependencies in an existing venv without recreating it.

        Raises RuntimeError if the venv does not exist.
        """
