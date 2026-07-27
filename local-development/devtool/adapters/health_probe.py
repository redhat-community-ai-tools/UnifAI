"""Adapter: network health probing via socket and urllib."""

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request

from devtool.ports.health_probe import HealthProbe


class NetworkHealthProbe(HealthProbe):
    """Concrete implementation that probes TCP ports and HTTP endpoints."""

    def check_port(self, host: str, port: int, timeout: float = 2.0) -> tuple[bool, float | None]:
        start = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                elapsed = (time.monotonic() - start) * 1000
                return True, round(elapsed, 1)
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False, None

    def check_http(
        self, host: str, port: int, path: str = "/", timeout: float = 3.0,
    ) -> tuple[bool, float | None]:
        url = f"http://{host}:{port}{path}"
        start = time.monotonic()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout):
                elapsed = (time.monotonic() - start) * 1000
                return True, round(elapsed, 1)
        except (urllib.error.URLError, OSError, TimeoutError):
            return False, None
