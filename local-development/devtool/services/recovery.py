"""Application service: dependency-aware restart engine."""

from __future__ import annotations

from devtool.domain.models import ContainerStatus, ServiceStatus
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.services.health_checker import HealthChecker
from devtool.ports.session_manager import SessionManager
from devtool.services.constants import SESSION_NAME


class Recovery:
    """Dependency-aware restart: checks infra first, then the service."""

    def __init__(
        self,
        registry: Registry,
        runtime: ContainerRuntime,
        session: SessionManager,
        health: HealthChecker,
    ) -> None:
        self._registry = registry
        self._runtime = runtime
        self._session = session
        self._health = health

    def restart_service(self, service_name: str) -> None:
        """Restart a single service after ensuring its infra is healthy."""
        svc = self._registry.get_service(service_name)
        print(f"\n🔄 Restarting {svc.name}…\n")

        infra = self._registry.infra_for_services([svc])
        restarted_infra: list[str] = []
        for comp in infra:
            st = self._runtime.status(comp)
            if st is not ContainerStatus.RUNNING:
                print(f"  ↻ Starting dependency: {comp.label}")
                self._runtime.ensure_running(comp)
                restarted_infra.append(comp.name)

        if restarted_infra:
            print(f"  Restarted infra: {', '.join(restarted_infra)}\n")

        if self._session.is_running(SESSION_NAME):
            if self._session.restart_service(SESSION_NAME, svc.name):
                print(f"  ✔ Sent restart signal to {svc.name}")
            else:
                print(f"  ⚠ Could not find pane for {svc.name}")
        else:
            print(f"  ⚠ No active session — start services first.")

    def restart_failed(self) -> None:
        """Scan all services and restart any that are unhealthy."""
        print("\n🔍 Scanning for failed services…\n")

        failed: list[str] = []
        for svc in self._registry.all_services():
            health = self._health.check_service(self._registry, svc.name)
            if svc.port and health.status not in (ServiceStatus.HEALTHY, ServiceStatus.NO_PORT):
                failed.append(svc.name)
                print(f"  ✖ {svc.name} — {health.status.value}")

        if not failed:
            print("  ✔ All services are healthy.")
            return

        primary_failed = [
            n for n in failed
            if self._registry.get_service(n).is_primary
        ]
        worker_failed = [
            n for n in failed
            if not self._registry.get_service(n).is_primary
        ]

        for name in primary_failed + worker_failed:
            self.restart_service(name)
