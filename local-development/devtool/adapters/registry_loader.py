"""Adapter: loads Registry from a YAML file + environment variables."""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    raise SystemExit(1)

from devtool.domain.models import (
    InfraComponent,
    ServiceInfo,
    ServiceGroup,
    ServiceType,
    VenvConfig,
    VenvStrategy,
)
from devtool.domain.registry import Registry

_DEFAULT_YAML = Path(__file__).resolve().parent.parent.parent / "services.yaml"


class YamlRegistryLoader:
    """Reads ``services.yaml`` and environment overrides, then builds a
    pure-domain :class:`Registry`."""

    @staticmethod
    def load(yaml_path: Path = _DEFAULT_YAML) -> Registry:
        with open(yaml_path) as fh:
            raw = yaml.safe_load(fh)

        env_val = os.environ.get("UNIFAI_LOCAL_AUTH", "").strip().lower()
        if env_val:
            local_auth = env_val in ("true", "1", "yes")
        else:
            local_auth = bool(raw.get("local_auth", True))

        min_override = (os.environ.get("PYTHON_MIN", "").strip() or None)
        max_override = (os.environ.get("PYTHON_MAX", "").strip() or None)
        python_min, python_max = YamlRegistryLoader._parse_python_bounds(
            raw, min_override=min_override, max_override=max_override,
        )

        return Registry(
            services=YamlRegistryLoader._parse_services(raw.get("services", {})),
            infra=YamlRegistryLoader._parse_infra(raw.get("infrastructure", {})),
            groups=YamlRegistryLoader._parse_groups(raw.get("groups", {})),
            local_auth=local_auth,
            python_min=python_min,
            python_max=python_max,
            log_dir=Path(
                raw.get("logging", {}).get("directory", "/tmp/unifai-dev/logs")
            ),
        )

    # -- parsing helpers (raw dict → domain model transforms) ----------------

    @staticmethod
    def _parse_infra(raw: dict) -> dict[str, InfraComponent]:
        result: dict[str, InfraComponent] = {}
        for name, data in raw.items():
            result[name] = InfraComponent(
                name=name,
                image=data["image"],
                ports=data.get("ports", []),
                label=data.get("label", name),
                command=data.get("command"),
                stop_timeout=data.get("stop_timeout"),
            )
        return result

    @staticmethod
    def _parse_services(raw: dict) -> dict[str, ServiceInfo]:
        result: dict[str, ServiceInfo] = {}
        for name, data in raw.items():
            venv_raw = data.get("venv", {})
            venv = VenvConfig(
                strategy=VenvStrategy(venv_raw.get("strategy", "none")),
                commands=venv_raw.get("commands", []),
            )
            result[name] = ServiceInfo(
                name=name,
                directory=Path(data["directory"]),
                port=data.get("port"),
                host=data.get("host"),
                health_endpoint=data.get("health_endpoint"),
                type=ServiceType(data.get("type", "python")),
                infrastructure=data.get("infrastructure", []),
                is_primary=data.get("is_primary", True),
                env_file=data.get("env_file"),
                env_entries=data.get("env_entries", {}),
                venv=venv,
                launch=data["launch"],
            )
        return result

    @staticmethod
    def _parse_groups(raw: dict) -> dict[str, ServiceGroup]:
        return {
            name: ServiceGroup(name=name, services=svc_list)
            for name, svc_list in raw.items()
        }

    @staticmethod
    def _parse_python_bounds(
        raw: dict,
        *,
        min_override: str | None = None,
        max_override: str | None = None,
    ) -> tuple[tuple[int, int], tuple[int, int]]:
        py = raw.get("python", {})
        min_str = min_override or py.get("min", "3.11")
        max_str = max_override or py.get("max", "3.13")
        min_parts = min_str.split(".")
        max_parts = max_str.split(".")
        return (
            (int(min_parts[0]), int(min_parts[1])),
            (int(max_parts[0]), int(max_parts[1])),
        )
