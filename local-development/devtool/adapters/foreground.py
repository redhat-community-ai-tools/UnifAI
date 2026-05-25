"""Adapter: foreground session manager for single-service mode."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devtool.domain.models import ServiceInfo, WindowLayout
from devtool.ports.session_manager import SessionManager
from devtool.utils import resolve_bash


class ForegroundSessionManager(SessionManager):
    """Runs a single primary service in the current terminal via exec."""

    def launch(
        self,
        session_name: str,
        layout: list[WindowLayout],
        commands: dict[str, str],
        log_dir: Path,
    ) -> None:
        all_services = [s for w in layout for s in w.services]
        if len(all_services) != 1:
            raise RuntimeError(
                "Foreground mode requires exactly one service, "
                f"got {len(all_services)}."
            )
        svc = all_services[0]
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{svc.name}.log"

        print(f"\n🚀 Starting {svc.name} …")
        print("   Press Ctrl+C to stop.\n")

        cmd = commands[svc.name]
        shell_cmd = f"{cmd} 2>&1 | tee {log_path}"
        bash = resolve_bash()
        sys.exit(subprocess.run([bash, "-c", shell_cmd]).returncode)

    def attach(self, session_name: str) -> None:
        pass

    def kill_session(self, session_name: str) -> None:
        pass

    def is_running(self, session_name: str) -> bool:
        return False

    def graceful_stop(self, session_name: str, timeout: int = 10) -> None:
        pass

    def pane_contents(self, session_name: str) -> dict[str, str]:
        return {}

    def select_pane(self, session_name: str, pane_ref: str) -> None:
        pass

    def restart_service(self, session_name: str, service_name: str) -> bool:
        return False
