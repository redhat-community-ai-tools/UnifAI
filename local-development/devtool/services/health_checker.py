"""Application service: health checking.

Probes service and infrastructure health via the HealthProbe port.
"""

from __future__ import annotations

from devtool.domain.models import (
    ContainerStatus,
    InfraComponent,
    InfraHealth,
    ServiceInfo,
    ServiceHealth,
    ServiceStatus,
    StatusIssue,
)
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.ports.health_probe import HealthProbe


class HealthChecker:
    """Probes service and infrastructure health via an injected HealthProbe."""

    def __init__(self, probe: HealthProbe) -> None:
        self._probe = probe

    # -- single-entity checks ------------------------------------------------

    def check_service(self, registry: Registry, service_name: str) -> ServiceHealth:
        """Check if a single service's port is reachable."""
        svc = registry.get_service(service_name)
        if not svc.port:
            return ServiceHealth(
                name=svc.name, status=ServiceStatus.NO_PORT, port=None, port_open=False,
            )

        host = self._resolve_host(svc)
        is_open, tcp_ms = self._probe.check_port(host, svc.port)

        if not is_open:
            return ServiceHealth(
                name=svc.name, status=ServiceStatus.DOWN, port=svc.port, port_open=False,
            )

        http_ok = False
        response_ms = tcp_ms
        if svc.health_endpoint:
            http_ok, http_ms = self._probe.check_http(host, svc.port, svc.health_endpoint)
            if http_ms is not None:
                response_ms = http_ms

        status = ServiceStatus.HEALTHY if (http_ok or not svc.health_endpoint) else ServiceStatus.UNHEALTHY
        return ServiceHealth(
            name=svc.name,
            status=status,
            port=svc.port,
            port_open=True,
            http_healthy=http_ok,
            response_time_ms=response_ms,
        )

    def check_infra(
        self, component: InfraComponent, runtime: ContainerRuntime,
    ) -> InfraHealth:
        """Check a single infrastructure component."""
        st = runtime.status(component)
        uptime = runtime.container_uptime(component) if st is ContainerStatus.RUNNING else None
        port = self._parse_host_port(component.ports[0]) if component.ports else None
        return InfraHealth(
            name=component.name,
            label=component.label,
            port=port,
            status=st,
            uptime=uptime,
        )

    # -- bulk checks ---------------------------------------------------------

    def check_all(
        self, registry: Registry, runtime: ContainerRuntime,
    ) -> tuple[list[InfraHealth], list[ServiceHealth]]:
        """Probe every infra component and service."""
        infra_results = [
            self.check_infra(comp, runtime)
            for comp in registry.all_infra()
        ]
        service_results = [
            self.check_service(registry, svc.name)
            for svc in registry.all_services()
        ]
        return infra_results, service_results

    # -- issue analysis -----------------------------------------

    def analyze_issues(
        self,
        registry: Registry,
        infra_results: list[InfraHealth],
        service_results: list[ServiceHealth],
    ) -> list[StatusIssue]:
        """Cross-reference infra and service health to generate actionable issues."""
        issues: list[StatusIssue] = []

        stopped_infra = {
            ih.name for ih in infra_results
            if ih.status is not ContainerStatus.RUNNING
        }

        for infra_name in stopped_infra:
            affected = [
                svc.name
                for svc in registry.all_services()
                if infra_name in svc.infrastructure
            ]
            comp = registry.get_infra(infra_name)
            desc = f"{comp.label} stopped"
            if affected:
                desc += f" \u2192 {' + '.join(affected)} affected"
            issues.append(StatusIssue(
                description=desc,
                fix=f"unifai-dev infra start {infra_name}",
                affected=affected,
            ))

        infra_caused: set[str] = set()
        for issue in issues:
            infra_caused.update(issue.affected)

        for sh in service_results:
            if sh.status in (ServiceStatus.HEALTHY, ServiceStatus.NO_PORT):
                continue
            if sh.name in infra_caused:
                continue
            if sh.status is ServiceStatus.UNHEALTHY:
                issues.append(StatusIssue(
                    description=f"{sh.name} health endpoint failing on port {sh.port}",
                    fix=f"unifai-dev restart {sh.name}",
                    affected=[sh.name],
                ))
            else:
                issues.append(StatusIssue(
                    description=f"{sh.name} not responding on port {sh.port}",
                    fix=f"unifai-dev restart {sh.name}",
                    affected=[sh.name],
                ))

        return issues

    # -- internal helpers ----------------------------------------------------

    @staticmethod
    def _resolve_host(svc: ServiceInfo) -> str:
        host = svc.host or "127.0.0.1"
        if host == "0.0.0.0":
            host = "127.0.0.1"
        return host

    @staticmethod
    def _parse_host_port(port_mapping: str) -> int | None:
        """Extract the host port from a mapping like ``"6379:6379"``."""
        try:
            return int(port_mapping.split(":")[0])
        except (ValueError, IndexError):
            return None
