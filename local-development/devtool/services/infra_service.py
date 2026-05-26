"""Application service: infrastructure container management."""

from __future__ import annotations

from devtool.domain.models import ContainerStatus
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime


class InfraService:

    def __init__(
        self,
        registry: Registry,
        container_runtime: ContainerRuntime,
    ) -> None:
        self._registry = registry
        self._runtime = container_runtime

    def start(
        self, targets: list[str] | None = None, *, for_service: str | None = None,
    ) -> None:
        self._registry.log_dir.mkdir(parents=True, exist_ok=True)
        self._runtime.set_log_file(self._registry.log_dir / "infra.log")
        print(f"Using container runtime: {self._runtime.runtime_name}\n")

        if for_service:
            svc = self._registry.get_service(for_service)
            components = self._registry.infra_for_services([svc])
            if not components:
                print(f"ℹ  Service '{for_service}' needs no infrastructure.")
                return
        elif targets:
            components = [self._registry.get_infra(t) for t in targets]
        else:
            components = self._registry.all_infra()

        print(f"Starting infrastructure: {', '.join(c.name for c in components)}\n")
        for comp in components:
            self._runtime.ensure_running(comp)
        print("\n✅ Infrastructure ready.")

    def stop(self) -> None:
        self._runtime.set_log_file(self._registry.log_dir / "infra.log")
        self._runtime.stop_all(self._registry.all_infra())

    def logs(
        self, component_name: str, *, follow: bool = False,
    ) -> None:
        comp = self._registry.get_infra(component_name)
        self._runtime.logs(comp, follow=follow)

    def reset(self, targets: list[str] | None = None) -> None:
        self._runtime.set_log_file(self._registry.log_dir / "infra.log")
        if targets:
            components = [self._registry.get_infra(t) for t in targets]
        else:
            components = self._registry.all_infra()

        print(f"Resetting: {', '.join(c.label for c in components)}\n")
        for comp in components:
            self._runtime.reset(comp)
        print("\n✅ Infrastructure reset complete.")

    def status(self) -> None:
        print("Infrastructure container status:")
        for comp in self._registry.all_infra():
            st = self._runtime.status(comp)
            if st is ContainerStatus.RUNNING:
                icon = "✔"
                label = "running"
            elif st is ContainerStatus.STOPPED:
                icon = "⏹"
                label = "stopped"
            else:
                icon = "✖"
                label = "not created"
            print(f"  {icon} {comp.label} ({comp.name}) — {label}")
