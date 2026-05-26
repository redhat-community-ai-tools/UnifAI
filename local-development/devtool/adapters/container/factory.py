"""Factory for detecting and creating the appropriate container runtime."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess

from devtool.adapters.container.base import SubprocessContainerRuntime
from devtool.adapters.container.docker import DockerRuntime
from devtool.adapters.container.podman import PodmanRuntime


class ContainerRuntimeFactory:
    """Discovers and creates the appropriate container runtime.

    Honours the ``UNIFAI_CONTAINER_RUNTIME`` environment variable.  When set,
    its value is used as the container command (e.g. ``sudo docker``) and
    auto-detection is skipped entirely.
    """

    @staticmethod
    def create() -> SubprocessContainerRuntime:
        """Return the first working container runtime (podman preferred)."""
        env_override = os.environ.get("UNIFAI_CONTAINER_RUNTIME")
        if env_override:
            return ContainerRuntimeFactory._from_env(env_override)

        runtime = ContainerRuntimeFactory._try_podman()
        if runtime:
            return runtime

        runtime = ContainerRuntimeFactory._try_docker()
        if runtime:
            return runtime

        raise RuntimeError(
            "No working container runtime found. Install Podman or Docker.\n"
            "If your runtime requires elevated privileges or a custom path, set\n"
            "  export UNIFAI_CONTAINER_RUNTIME='<command>'  "
            "(e.g. 'sudo docker')"
        )

    @staticmethod
    def _from_env(value: str) -> SubprocessContainerRuntime:
        cmd = shlex.split(value)
        result = subprocess.run([*cmd, "info"], capture_output=True)
        if result.returncode == 0:
            return SubprocessContainerRuntime(cmd)
        raise RuntimeError(
            f"UNIFAI_CONTAINER_RUNTIME is set to '{value}' "
            f"but '{value} info' failed. "
            f"Verify the command works in your terminal."
        )

    @staticmethod
    def _try_podman() -> PodmanRuntime | None:
        if not shutil.which("podman"):
            return None

        result = subprocess.run(
            ["podman", "info"],
            capture_output=True,
        )
        if result.returncode == 0:
            return PodmanRuntime()

        machines = subprocess.run(
            ["podman", "machine", "list", "--format", "{{.Name}}"],
            capture_output=True, text=True,
        )
        if machines.stdout.strip():
            subprocess.run(
                ["podman", "machine", "start"],
                capture_output=True,
            )
            check = subprocess.run(
                ["podman", "info"],
                capture_output=True,
            )
            if check.returncode == 0:
                return PodmanRuntime()

        return None

    @staticmethod
    def _try_docker() -> DockerRuntime | None:
        if not shutil.which("docker"):
            return None

        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
        )
        if result.returncode == 0:
            return DockerRuntime()

        return None
