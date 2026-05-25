"""Application service: orchestrator facade — thin delegation layer."""

from __future__ import annotations

import shutil
from pathlib import Path

from devtool.domain.models import ContainerStatus, ServiceType
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.services.health_checker import HealthChecker
from devtool.ports.session_manager import SessionManager
from devtool.services.constants import SESSION_NAME
from devtool.services.diagnostic_service import DiagnosticService
from devtool.services.pane_matcher import match_panes_to_services
from devtool.services.env_service import EnvService
from devtool.services.infra_service import InfraService
from devtool.services.init_service import InitService
from devtool.services.recovery import Recovery
from devtool.services.startup_service import StartupService
from devtool.services.venv_service import VenvService


class Orchestrator:
    """Thin facade that delegates to focused service classes."""

    def __init__(
        self,
        registry: Registry,
        root: Path,
        container_runtime: ContainerRuntime,
        session_manager: SessionManager,
        health_checker: HealthChecker,
        startup_service: StartupService,
        infra_service: InfraService,
        venv_service: VenvService,
        env_service: EnvService,
        diagnostic_service: DiagnosticService,
        init_service: InitService,
    ) -> None:
        self._registry = registry
        self._root = root
        self._runtime = container_runtime
        self._session = session_manager
        self._health = health_checker
        self._startup = startup_service
        self._infra = infra_service
        self._venv_svc = venv_service
        self._env_svc = env_service
        self._diag = diagnostic_service
        self._init = init_service

    # -- start / shell / exec ------------------------------------------------

    def start(
        self,
        targets: list[str] | None = None,
        *,
        fg: bool = False,
        setup_venv: bool = False,
        window_specs: list[tuple[str | None, list[str]]] | None = None,
    ) -> None:
        self._startup.start(
            targets, fg=fg, setup_venv=setup_venv, window_specs=window_specs,
        )

    def attach(self, service_name: str) -> None:
        """Jump to the tmux pane running a specific service."""
        if not self._session.is_running(SESSION_NAME):
            print(f"No session '{SESSION_NAME}' running. Start services first.")
            return

        svc = self._registry.get_service(service_name)
        pane_contents = self._session.pane_contents(SESSION_NAME)
        mapping = match_panes_to_services([svc], pane_contents)

        pane_ref = mapping.get(svc.name)
        if not pane_ref:
            print(f"Could not find a tmux pane for '{svc.name}'.")
            return

        self._session.select_pane(SESSION_NAME, pane_ref)
        self._session.attach(SESSION_NAME)

    def shell(self, service_name: str) -> None:
        self._startup.shell(service_name)

    def exec_in_context(self, service_name: str, command: list[str]) -> int:
        return self._startup.exec_in_context(service_name, command)

    # -- stop / destroy ------------------------------------------------------

    def stop(self) -> None:
        if self._session.is_running(SESSION_NAME):
            self._session.kill_session(SESSION_NAME)
            print(f"Session '{SESSION_NAME}' destroyed.")
        else:
            print(f"No session '{SESSION_NAME}' found.")

    def destroy(self) -> None:
        if self._session.is_running(SESSION_NAME):
            print("Gracefully stopping services…")
            self._session.graceful_stop(SESSION_NAME)
            print("Services stopped.")
        else:
            print(f"No session '{SESSION_NAME}' found.")
        print("\nStopping infrastructure…")
        self._runtime.set_log_file(self._registry.log_dir / "infra.log")
        self._runtime.stop_all(self._registry.all_infra())

    # -- infra subcommands ---------------------------------------------------

    def infra_start(
        self, targets: list[str] | None = None, *, for_service: str | None = None,
    ) -> None:
        self._infra.start(targets, for_service=for_service)

    def infra_stop(self) -> None:
        self._infra.stop()

    def infra_logs(self, component_name: str, *, follow: bool = False) -> None:
        self._infra.logs(component_name, follow=follow)

    def infra_reset(self, targets: list[str] | None = None) -> None:
        self._infra.reset(targets)

    def infra_status(self) -> None:
        self._infra.status()

    # -- venv subcommands ----------------------------------------------------

    def venv_setup(self, service_name: str | None = None, *, force: bool = False) -> None:
        self._venv_svc.setup(service_name, force=force)

    def venv_sync(self, service_name: str | None = None) -> None:
        self._venv_svc.sync(service_name)

    def venv_check(self) -> list[str]:
        return self._venv_svc.check()

    # -- env subcommands -----------------------------------------------------

    def env_generate(self, *, force: bool = False) -> None:
        self._env_svc.generate(force=force)

    def env_show(self, service_name: str) -> None:
        self._env_svc.show(service_name)

    # -- diagnostics ---------------------------------------------------------

    def logs(self, service_name: str, *, follow: bool = False) -> None:
        self._diag.logs(service_name, follow=follow)

    def status(self) -> None:
        self._diag.status()

    def doctor(self) -> None:
        self._diag.doctor()

    # -- restart -------------------------------------------------------------

    def restart(self, targets: list[str] | None = None, *, failed: bool = False) -> None:
        recovery = Recovery(
            self._registry, self._runtime, self._session, self._health,
        )

        if failed:
            recovery.restart_failed()
        elif targets:
            services = self._registry.resolve_services(targets)
            for svc in services:
                recovery.restart_service(svc.name)
        else:
            print("Specify service/group names or use --failed.")

    # -- init ----------------------------------------------------------------

    def init(self, *, non_interactive: bool = False) -> None:
        self._init.init(non_interactive=non_interactive)

    # -- clean ---------------------------------------------------------------

    def clean(
        self,
        *,
        dry_run: bool = False,
        clean_logs: bool = True,
        clean_venvs: bool = False,
        clean_containers: bool = True,
    ) -> None:
        """Remove stale resources: log files, stopped containers, venvs."""
        removed: list[str] = []

        if clean_logs:
            log_dir = self._registry.log_dir
            if log_dir.is_dir():
                for f in sorted(log_dir.iterdir()):
                    if f.is_file():
                        label = f"log: {f.name}"
                        if dry_run:
                            print(f"  (would remove) {label}")
                        else:
                            f.unlink()
                            print(f"  ✔ Removed {label}")
                        removed.append(label)

        if clean_containers:
            self._runtime.set_log_file(self._registry.log_dir / "infra.log")
            for comp in self._registry.all_infra():
                st = self._runtime.status(comp)
                if st is ContainerStatus.STOPPED:
                    label = f"container: {comp.label} ({comp.name})"
                    if dry_run:
                        print(f"  (would remove) {label}")
                    else:
                        self._runtime.remove(comp)
                        print(f"  ✔ Removed {label}")
                    removed.append(label)

        if clean_venvs:
            existing = self._venv_svc.existing_venvs(
                self._registry.primary_services(),
            )
            for svc in existing:
                svc_dir = self._root / svc.directory
                venv_dir = svc_dir / ("node_modules" if svc.type is ServiceType.NODE else "venv")
                label = f"venv: {svc.name} ({venv_dir})"
                if dry_run:
                    print(f"  (would remove) {label}")
                else:
                    shutil.rmtree(venv_dir)
                    print(f"  ✔ Removed {label}")
                removed.append(label)

        if not removed:
            print("  Nothing to clean.")
        elif dry_run:
            print(f"\n  {len(removed)} item(s) would be removed. "
                  f"Run without --dry-run to proceed.")
        else:
            print(f"\n  ✔ Cleaned {len(removed)} item(s).")
