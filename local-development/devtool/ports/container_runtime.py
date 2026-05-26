"""Port: container runtime for managing infrastructure containers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from devtool.domain.models import ContainerStatus, InfraComponent


class ContainerRuntime(ABC):

    @abstractmethod
    def ensure_running(self, component: InfraComponent) -> None:
        """Start the container if it is not already running."""

    @abstractmethod
    def stop(self, component: InfraComponent) -> None:
        """Stop a running container."""

    @abstractmethod
    def status(self, component: InfraComponent) -> ContainerStatus:
        """Return the current status of the container."""

    @abstractmethod
    def stop_all(self, components: list[InfraComponent]) -> None:
        """Stop all given containers."""

    @property
    @abstractmethod
    def runtime_name(self) -> str:
        """Human-readable name of the container runtime (e.g. 'podman')."""

    @abstractmethod
    def set_log_file(self, path: Path) -> None:
        """Set the file where runtime logs are appended."""

    @abstractmethod
    def container_uptime(self, component: InfraComponent) -> str | None:
        """Return a human-readable uptime string, or None if not running."""

    @abstractmethod
    def logs(self, component: InfraComponent, *, follow: bool = False) -> None:
        """Stream container logs to stdout."""

    @abstractmethod
    def remove(self, component: InfraComponent) -> None:
        """Remove a stopped container (and its volumes)."""

    @abstractmethod
    def reset(self, component: InfraComponent) -> None:
        """Stop, remove, and recreate a container."""
