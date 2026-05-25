"""Base class that drives either ``podman`` or ``docker`` via subprocess."""

from __future__ import annotations

import contextlib
import shlex
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from devtool.domain.models import ContainerStatus, InfraComponent
from devtool.ports.container_runtime import ContainerRuntime
from devtool.utils import format_duration


class SubprocessContainerRuntime(ContainerRuntime):
    """Base class that drives either ``podman`` or ``docker`` via subprocess."""

    def __init__(self, cmd: list[str] | str) -> None:
        self._cmd: list[str] = [cmd] if isinstance(cmd, str) else list(cmd)
        self._log_file: Path | None = None

    @property
    def runtime_name(self) -> str:
        return " ".join(self._cmd)

    def set_log_file(self, path: Path) -> None:
        self._log_file = path

    # -- ContainerRuntime implementation -------------------------------------

    def ensure_running(self, component: InfraComponent) -> None:
        current = self.status(component)
        if current is ContainerStatus.RUNNING:
            print(f"  ✔ {component.label} is already running.")
            return

        if current is ContainerStatus.STOPPED:
            print(f"  ↻ Starting stopped {component.label} container…")
            self._run([*self._cmd, "start", component.name])
        else:
            print(f"  ⊕ Creating {component.label} container…")
            cmd: list[str] = [*self._cmd, "run", "-d", "--name", component.name]
            for port_map in component.ports:
                cmd.extend(["-p", port_map])
            cmd.append(component.image)
            if component.command:
                cmd.extend(shlex.split(component.command))
            self._run(cmd)

        self._verify_running(component)

    def stop(self, component: InfraComponent) -> None:
        if self.status(component) is ContainerStatus.RUNNING:
            cmd = [*self._cmd, "stop"]
            if component.stop_timeout:
                cmd.extend(["--time", str(component.stop_timeout)])
            cmd.append(component.name)
            self._run(cmd)
            print(f"  ⏹ {component.label} stopped.")

    def status(self, component: InfraComponent) -> ContainerStatus:
        if self._is_listed(component.name, running_only=True):
            return ContainerStatus.RUNNING
        if self._is_listed(component.name, running_only=False):
            return ContainerStatus.STOPPED
        return ContainerStatus.NOT_CREATED

    def stop_all(self, components: list[InfraComponent]) -> None:
        print("Stopping infrastructure containers…")
        for comp in components:
            self.stop(comp)

    def container_uptime(self, component: InfraComponent) -> str | None:
        if self.status(component) is not ContainerStatus.RUNNING:
            return None
        result = subprocess.run(
            [
                *self._cmd, "inspect",
                "--format", "{{.State.StartedAt}}",
                component.name,
            ],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        try:
            raw = result.stdout.strip()
            started = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - started
            return format_duration(delta)
        except (ValueError, TypeError):
            return None

    def logs(self, component: InfraComponent, *, follow: bool = False) -> None:
        cmd = [*self._cmd, "logs"]
        if follow:
            cmd.append("-f")
        cmd.append(component.name)
        subprocess.run(cmd)

    def remove(self, component: InfraComponent) -> None:
        st = self.status(component)
        if st is ContainerStatus.RUNNING:
            self.stop(component)
        if self._is_listed(component.name, running_only=False):
            subprocess.run(
                [*self._cmd, "rm", "-v", component.name],
                capture_output=True, check=False,
            )
            print(f"  ⊖ {component.label} removed.")

    def reset(self, component: InfraComponent) -> None:
        """Stop, remove, and recreate a container from scratch."""
        print(f"  ↻ Resetting {component.label}…")
        self.remove(component)
        self.ensure_running(component)

    # -- helpers -------------------------------------------------------------

    def _verify_running(
        self, component: InfraComponent, wait: float = 2.0,
    ) -> None:
        time.sleep(wait)
        if self.status(component) is not ContainerStatus.RUNNING:
            exit_code = self._get_exit_code(component)
            raise RuntimeError(
                f"{component.label} exited shortly after starting "
                f"(exit={exit_code}). "
                f"Check: {self.runtime_name} logs {component.name}"
            )
        print(f"  ✔ {component.label} started.")

    def _get_exit_code(self, component: InfraComponent) -> int | None:
        result = subprocess.run(
            [
                *self._cmd, "inspect",
                "--format", "{{.State.ExitCode}}",
                component.name,
            ],
            capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
        return None

    def _is_listed(self, name: str, *, running_only: bool) -> bool:
        cmd = [*self._cmd, "ps"]
        if not running_only:
            cmd.append("-a")
        cmd.extend(["--format", "{{.Names}}"])
        result = subprocess.run(
            cmd, capture_output=True, text=True,
        )
        return name in result.stdout.splitlines()

    def _run(self, cmd: list[str]) -> None:
        with contextlib.ExitStack() as stack:
            if self._log_file:
                stderr_dest = stack.enter_context(open(self._log_file, "a"))
            else:
                stderr_dest = subprocess.DEVNULL
            try:
                subprocess.run(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_dest,
                    check=True,
                )
            except subprocess.CalledProcessError:
                log_hint = f" Check {self._log_file}" if self._log_file else ""
                print(f"  ⚠ Command failed: {' '.join(cmd)}.{log_hint}")
                raise
