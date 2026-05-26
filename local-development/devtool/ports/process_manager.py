"""Port: process and port management."""

from __future__ import annotations

from abc import ABC, abstractmethod

from devtool.domain.models import PortOccupant


class ProcessManager(ABC):

    @abstractmethod
    def find_port_occupants(self, port: int) -> list[PortOccupant]:
        """Return PIDs and process names listening on *port*."""

    @abstractmethod
    def is_port_in_use(self, port: int) -> bool:
        """Return True if any process is bound to *port*."""

    @abstractmethod
    def kill_processes(
        self, pids: list[int], *, graceful_timeout: float = 0.5,
    ) -> None:
        """Send SIGTERM, wait *graceful_timeout*, then SIGKILL survivors."""
