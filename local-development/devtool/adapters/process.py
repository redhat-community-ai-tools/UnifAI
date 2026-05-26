"""Adapter: local process manager using OS-specific tools."""

from __future__ import annotations

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

from devtool.domain.models import PortOccupant
from devtool.ports.process_manager import ProcessManager


class LocalProcessManager(ProcessManager):
    """Discovers and kills local processes via lsof / ss / /proc."""

    def find_port_occupants(self, port: int) -> list[PortOccupant]:
        if shutil.which("lsof"):
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                occupants: list[PortOccupant] = []
                for line in result.stdout.strip().splitlines():
                    try:
                        pid = int(line.strip())
                        occupants.append(PortOccupant(pid, self._read_proc_name(pid)))
                    except ValueError:
                        pass
                return occupants

        if shutil.which("ss"):
            result = subprocess.run(
                ["ss", "-tlnp", f"sport = :{port}"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                occupants = []
                for m in re.finditer(
                    r'\("([^"]*)",pid=(\d+)', result.stdout,
                ):
                    occupants.append(
                        PortOccupant(int(m.group(2)), m.group(1)),
                    )
                return occupants

        try:
            return self._find_pids_from_proc(port)
        except (OSError, PermissionError):
            pass

        return []

    def is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("127.0.0.1", port)) == 0

    def kill_processes(
        self, pids: list[int], *, graceful_timeout: float = 0.5,
    ) -> None:
        unique_pids = dict.fromkeys(pids)
        for pid in unique_pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(graceful_timeout)
        for pid in unique_pids:
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _read_proc_name(pid: int) -> str:
        """Best-effort process name via /proc (Linux) or ps (macOS/BSD)."""
        try:
            return Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            pass
        try:
            out = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True, text=True,
            )
            name = out.stdout.strip()
            if name:
                return name
        except OSError:
            pass
        return "unknown"

    def _find_pids_from_proc(self, port: int) -> list[PortOccupant]:
        """Parse /proc/net/tcp to find PIDs bound to *port* (Linux-only fallback)."""
        hex_port = f"{port:04X}"
        inodes: set[str] = set()

        for proto in ("/proc/net/tcp", "/proc/net/tcp6"):
            try:
                with open(proto) as f:
                    for line in f:
                        fields = line.split()
                        if len(fields) < 10:
                            continue
                        local_addr = fields[1]
                        local_port = local_addr.split(":")[1]
                        if local_port == hex_port:
                            inodes.add(fields[9])
            except FileNotFoundError:
                continue

        if not inodes:
            return []

        results: list[PortOccupant] = []
        for pid_dir in Path("/proc").iterdir():
            if not pid_dir.name.isdigit():
                continue
            fd_dir = pid_dir / "fd"
            try:
                for fd in fd_dir.iterdir():
                    try:
                        link = os.readlink(str(fd))
                    except OSError:
                        continue
                    if link.startswith("socket:["):
                        inode = link[8:-1]
                        if inode in inodes:
                            pid = int(pid_dir.name)
                            results.append(
                                PortOccupant(pid, self._read_proc_name(pid)),
                            )
                            break
            except PermissionError:
                continue

        return results
