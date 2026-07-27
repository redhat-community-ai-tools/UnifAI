"""Registry — pure domain: typed lookups over pre-parsed service data."""

from __future__ import annotations

from pathlib import Path

from .models import (
    InfraComponent,
    ServiceInfo,
    ServiceGroup,
    ServiceType,
)


class Registry:
    """Single source of truth for services, infra, and groups.

    Constructed from pre-parsed data — no file I/O, no environment
    variables, no external library dependencies.
    """

    def __init__(
        self,
        *,
        services: dict[str, ServiceInfo],
        infra: dict[str, InfraComponent],
        groups: dict[str, ServiceGroup],
        local_auth: bool,
        python_min: tuple[int, int],
        python_max: tuple[int, int],
        node_min: int | None = None,
        log_dir: Path,
    ) -> None:
        self._services = services
        self._infra = infra
        self._groups = groups
        self._local_auth = local_auth
        self._python_min = python_min
        self._python_max = python_max
        self._node_min = node_min
        self._log_dir = log_dir

    # -- public API ----------------------------------------------------------

    def get_service(self, name: str) -> ServiceInfo:
        if name not in self._services:
            raise KeyError(
                f"Unknown service '{name}'. "
                f"Known services: {', '.join(self._services)}"
            )
        return self._services[name]

    def get_infra(self, name: str) -> InfraComponent:
        if name not in self._infra:
            raise KeyError(
                f"Unknown infrastructure '{name}'. "
                f"Known: {', '.join(self._infra)}"
            )
        return self._infra[name]

    def all_services(self) -> list[ServiceInfo]:
        return list(self._services.values())

    def all_infra(self) -> list[InfraComponent]:
        return list(self._infra.values())

    def primary_services(self) -> list[ServiceInfo]:
        seen_dirs: set[Path] = set()
        result: list[ServiceInfo] = []
        for svc in self._services.values():
            if not svc.is_primary:
                continue
            if svc.directory in seen_dirs:
                continue
            seen_dirs.add(svc.directory)
            result.append(svc)
        return result

    def get_group(self, name: str) -> ServiceGroup:
        if name not in self._groups:
            raise KeyError(
                f"Unknown group '{name}'. "
                f"Known groups: {', '.join(self._groups)}"
            )
        return self._groups[name]

    def service_names(self) -> list[str]:
        return list(self._services.keys())

    def group_names(self) -> list[str]:
        return list(self._groups.keys())

    def infra_names(self) -> list[str]:
        return list(self._infra.keys())

    def groups_for_service(self, name: str) -> list[str]:
        """Return the names of all groups that contain *name*."""
        return [
            g.name for g in self._groups.values()
            if name in g.services
        ]

    def resolve_services(self, targets: list[str]) -> list[ServiceInfo]:
        """Expand a mix of service names and group names into a
        deduplicated list of ServiceInfo objects, preserving first-seen order."""
        seen: set[str] = set()
        result: list[ServiceInfo] = []
        for target in targets:
            if target in self._groups:
                for svc_name in self._groups[target].services:
                    if svc_name not in seen:
                        seen.add(svc_name)
                        result.append(self.get_service(svc_name))
            else:
                if target not in seen:
                    seen.add(target)
                    result.append(self.get_service(target))
        return result

    def infra_for_services(self, services: list[ServiceInfo]) -> list[InfraComponent]:
        """Union of all infrastructure needed by the given services."""
        seen: set[str] = set()
        result: list[InfraComponent] = []
        for svc in services:
            for name in svc.infrastructure:
                if name not in seen:
                    seen.add(name)
                    result.append(self.get_infra(name))
        return result

    def python_bounds(self) -> tuple[tuple[int, int], tuple[int, int]]:
        return self._python_min, self._python_max

    @property
    def node_min(self) -> int | None:
        return self._node_min

    def has_node_services(self) -> bool:
        return any(
            s.type is ServiceType.NODE for s in self._services.values()
        )

    @property
    def local_auth(self) -> bool:
        return self._local_auth

    @property
    def log_dir(self) -> Path:
        return self._log_dir
