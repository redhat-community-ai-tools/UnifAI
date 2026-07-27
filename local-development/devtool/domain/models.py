"""Domain models — pure data, no external dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ServiceType(Enum):
    PYTHON = "python"
    NODE = "node"


class VenvStrategy(Enum):
    REQUIREMENTS = "requirements"
    TOML = "toml"
    CUSTOM = "custom"
    NODE = "node"
    NONE = "none"


class ContainerStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_CREATED = "not_created"


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DOWN = "down"
    NO_PORT = "no_port"


@dataclass(frozen=True)
class InfraComponent:
    name: str
    image: str
    ports: list[str]
    label: str
    command: str | None = None
    stop_timeout: int | None = None


@dataclass(frozen=True)
class VenvConfig:
    strategy: VenvStrategy
    commands: list[str] = field(default_factory=list)
    global_utils_extra: str | None = None
    pip_extras: str | None = None


@dataclass(frozen=True)
class ServiceInfo:
    name: str
    directory: Path
    type: ServiceType
    launch: str
    venv: VenvConfig
    port: int | None = None
    host: str | None = None
    health_endpoint: str | None = None
    infrastructure: list[str] = field(default_factory=list)
    is_primary: bool = True
    env_file: str | None = None
    env_entries: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ServiceGroup:
    name: str
    services: list[str]


@dataclass(frozen=True)
class WindowLayout:
    name: str
    services: list[ServiceInfo]


@dataclass(frozen=True)
class ServiceHealth:
    name: str
    status: ServiceStatus
    port: int | None
    port_open: bool
    http_healthy: bool = False
    response_time_ms: float | None = None
    tmux_pane: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class InfraHealth:
    name: str
    label: str
    port: int | None
    status: ContainerStatus
    uptime: str | None = None


@dataclass(frozen=True)
class PortOccupant:
    pid: int
    name: str


@dataclass(frozen=True)
class StatusIssue:
    description: str
    fix: str
    affected: list[str] = field(default_factory=list)
