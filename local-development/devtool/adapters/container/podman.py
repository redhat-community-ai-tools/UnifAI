"""Adapter: Podman container runtime."""

from __future__ import annotations

from devtool.adapters.container.base import SubprocessContainerRuntime


class PodmanRuntime(SubprocessContainerRuntime):
    def __init__(self) -> None:
        super().__init__("podman")
