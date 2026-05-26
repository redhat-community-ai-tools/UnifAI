"""Port: network probing for health checks (TCP and HTTP)."""

from __future__ import annotations

from abc import ABC, abstractmethod


class HealthProbe(ABC):

    @abstractmethod
    def check_port(self, host: str, port: int, timeout: float = 2.0) -> tuple[bool, float | None]:
        """Probe a TCP port.

        Returns ``(is_open, response_time_ms)`` or ``(False, None)`` on failure.
        """

    @abstractmethod
    def check_http(
        self, host: str, port: int, path: str = "/", timeout: float = 3.0,
    ) -> tuple[bool, float | None]:
        """HTTP GET against a health endpoint.

        Returns ``(is_ok, response_time_ms)`` or ``(False, None)`` on failure.
        """
