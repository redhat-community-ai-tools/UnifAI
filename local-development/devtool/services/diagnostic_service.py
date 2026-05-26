"""Application service: health status and diagnostics."""

from __future__ import annotations

import subprocess
from pathlib import Path

from devtool.domain.models import (
    ContainerStatus,
    InfraHealth,
    ServiceHealth,
    ServiceStatus,
    StatusIssue,
)
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.ports.process_manager import ProcessManager
from devtool.ports.session_manager import SessionManager
from devtool.services.constants import SESSION_NAME
from devtool.services.env_service import EnvService
from devtool.services.health_checker import HealthChecker
from devtool.services.infra_service import InfraService
from devtool.services.pane_matcher import match_panes_to_services
from devtool.services.venv_service import VenvService


class DiagnosticService:

    def __init__(
        self,
        registry: Registry,
        root: Path,
        runtime: ContainerRuntime,
        session: SessionManager,
        process_manager: ProcessManager,
        health_checker: HealthChecker,
        infra_service: InfraService,
        venv_service: VenvService,
        env_service: EnvService,
    ) -> None:
        self._registry = registry
        self._root = root
        self._runtime = runtime
        self._session = session
        self._process = process_manager
        self._health = health_checker
        self._infra_svc = infra_service
        self._venv_svc = venv_service
        self._env_svc = env_service

    def status(self) -> None:
        infra, services = self._health.check_all(self._registry, self._runtime)

        pane_contents = self._session.pane_contents(SESSION_NAME)
        pane_mapping = match_panes_to_services(
            self._registry.all_services(), pane_contents,
        )
        enriched = [
            ServiceHealth(
                name=sh.name,
                status=sh.status,
                port=sh.port,
                port_open=sh.port_open,
                http_healthy=sh.http_healthy,
                response_time_ms=sh.response_time_ms,
                tmux_pane=f"tmux:{pane_mapping[sh.name]}" if sh.name in pane_mapping else None,
                error=sh.error,
            )
            for sh in services
        ]

        issues = self._health.analyze_issues(self._registry, infra, enriched)
        self._render_dashboard(infra, enriched, issues)

    def doctor(self) -> None:
        print("🩺 Running diagnostics…\n")

        try:
            python, python_minor = self._venv_svc.detect_python()
            print(f"  ✔ Python: {python} ({python_minor})")
        except RuntimeError as exc:
            print(f"  ✖ Python: {exc}")

        print(f"  ✔ Container runtime: {self._runtime.runtime_name}")

        print()
        self._infra_svc.status()

        print("\nVirtual environments:")
        venv_errors = self._venv_svc.check()

        print("\nEnvironment files:")
        for svc in self._registry.all_services():
            if svc.env_file:
                rel = svc.directory / svc.env_file
                if self._env_svc.env_file_exists(svc):
                    print(f"  ✔ {svc.name}: {rel}")
                    missing = self._env_svc.check_missing_keys(svc)
                    for key in sorted(missing):
                        print(f"  ⚠ {svc.name}: {rel}  {key} is missing (run 'unifai-dev start' or 'unifai-dev env generate')")
                    placeholders, auto_gen = self._env_svc.check_unresolved(svc)
                    for key in placeholders:
                        print(f"  ⚠ {svc.name}: {rel}  {key} is still a placeholder!")
                    for key in auto_gen:
                        print(f"  ⚠ {svc.name}: {rel}  {key} is unresolved (run 'unifai-dev init' or 'unifai-dev env generate --force')")
                else:
                    if svc.env_entries:
                        print(f"  ✖ {svc.name}: {rel} missing")
                        print(f"    💡 Tip: run 'unifai-dev env generate' to generate the .env file.")
                    else:
                        print(f"  ✔ {svc.name}: {rel} shouldn't exist")

        print("\nPort availability:")
        for svc in self._registry.all_services():
            if svc.port:
                in_use = self._process.is_port_in_use(svc.port)
                icon = "⚠ in use" if in_use else "✔ free"
                print(f"  {icon}: port {svc.port} ({svc.name})")

    def logs(self, service_name: str, *, follow: bool = False) -> None:
        log_path = self._registry.log_dir / f"{service_name}.log"
        if not log_path.exists():
            print(f"No log file found at {log_path}")
            return

        cmd = ["tail", "-f", str(log_path)] if follow else ["cat", str(log_path)]
        subprocess.run(cmd)

    @staticmethod
    def _render_dashboard(
        infra_results: list[InfraHealth],
        service_results: list[ServiceHealth],
        issues: list[StatusIssue],
    ) -> None:
        """Print a human-friendly status dashboard to stdout."""

        print()
        print("  INFRASTRUCTURE")
        for ih in infra_results:
            port_str = f":{ih.port}" if ih.port else ""
            if ih.status is ContainerStatus.RUNNING:
                uptime_str = f"  (up {ih.uptime})" if ih.uptime else ""
                print(f"  ✔ {ih.label:<14}{port_str:<10}running{uptime_str}")
            elif ih.status is ContainerStatus.STOPPED:
                print(f"  ✖ {ih.label:<14}{port_str:<10}STOPPED")
            else:
                print(f"  ✖ {ih.label:<14}{port_str:<10}NOT CREATED")

        print()
        print("  SERVICES")
        for sh in service_results:
            port_str = f":{sh.port}" if sh.port else ""
            pane_str = f"  {sh.tmux_pane}" if sh.tmux_pane else ""
            if sh.status is ServiceStatus.HEALTHY:
                rt = f"  ({sh.response_time_ms}ms)" if sh.response_time_ms else ""
                print(f"  ✔ {sh.name:<14}{port_str:<10}healthy{rt}{pane_str}")
            elif sh.status is ServiceStatus.NO_PORT:
                status_label = "worker" if pane_str else "no port"
                print(f"  ─ {sh.name:<14}{'':<10}{status_label}{pane_str}")
            elif sh.status is ServiceStatus.UNHEALTHY:
                rt = f"  ({sh.response_time_ms}ms)" if sh.response_time_ms else ""
                print(f"  ⚠ {sh.name:<14}{port_str:<10}unhealthy{rt}{pane_str}")
            else:
                print(f"  ✖ {sh.name:<14}{port_str:<10}DOWN{pane_str}")

        if issues:
            print()
            print("  ISSUES")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue.description}")
                print(f"     Fix: {issue.fix}")
        print()
