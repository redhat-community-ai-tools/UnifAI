"""Application service: start flow orchestration."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from devtool.domain.models import (
    InfraComponent,
    PortOccupant,
    ServiceInfo,
    ServiceType,
    WindowLayout,
)
from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.ports.process_manager import ProcessManager
from devtool.ports.session_manager import SessionManager
from devtool.services.constants import SESSION_NAME
from devtool.services.env_service import EnvService
from devtool.utils import resolve_bash
from devtool.services.venv_service import VenvService


class StartupService:

    def __init__(
        self,
        registry: Registry,
        root: Path,
        container_runtime: ContainerRuntime,
        session_manager: SessionManager,
        process_manager: ProcessManager,
        venv_service: VenvService,
        env_service: EnvService,
    ) -> None:
        self._registry = registry
        self._root = root
        self._runtime = container_runtime
        self._session = session_manager
        self._process = process_manager
        self._venv_svc = venv_service
        self._env_svc = env_service

    def start(
        self,
        targets: list[str] | None = None,
        *,
        fg: bool = False,
        setup_venv: bool = False,
        window_specs: list[tuple[str | None, list[str]]] | None = None,
    ) -> None:
        if not targets and not window_specs:
            targets = ["all"]

        if window_specs and targets:
            all_names: list[str] = list(targets)
            for _, names in window_specs:
                all_names.extend(names)
            services = self._registry.resolve_services(all_names)
        elif window_specs:
            services = self._registry.resolve_services(["all"])
        else:
            services = self._registry.resolve_services(targets or ["all"])

        self._validate_start(services, fg=fg)

        python, python_minor = self._venv_svc.detect_python()

        # 1. Infrastructure
        infra = self._registry.infra_for_services(services)
        if infra:
            log_dir = self._registry.log_dir
            log_dir.mkdir(parents=True, exist_ok=True)
            self._runtime.set_log_file(log_dir / "infra.log")
            print(f"\nUsing container runtime: {self._runtime.runtime_name}")
            print(f"\nStarting infrastructure: {', '.join(c.name for c in infra)}\n")
            for comp in infra:
                self._runtime.ensure_running(comp)
            print("\n✅ Infrastructure ready.\n")
            time.sleep(1)

        # 2. Venv setup (optional)
        if setup_venv:
            print("📦 Setting up virtual environments…\n")
            primaries = [s for s in services if s.is_primary]
            self._venv_svc.setup_services(primaries, python)
            print()

        # 3. Env generation + auto-generate resolution
        self._env_svc.generate()
        self._env_svc.auto_resolve_generated_keys()
        print()

        # 4. Verify venvs
        python_svcs = [
            s for s in services
            if s.is_primary and s.type is ServiceType.PYTHON
        ]
        self._venv_svc.verify_services(python_svcs, python_minor)

        # 5. Check/free ports
        conflicting = self._check_ports(services)

        if conflicting:
            print(
                "\n  ┌─────────────────────────────────────────────────────┐"
                "\n  │  WARNING: ports still in use!                      │"
                "\n  │  The following services will likely fail to start:  │"
            )
            for name in conflicting:
                print(f"  │    - {name:<47}│")
            print(
                "  │                                                     │"
                "\n  │  To fix: stop the conflicting processes manually   │"
                "\n  │  and run 'unifai-dev restart --failed'.            │"
                "\n  └─────────────────────────────────────────────────────┘"
            )
            try:
                input("\n  Press Enter to continue…")
            except EOFError:
                pass

        # 6. Build shell commands
        commands = self._build_commands(services, python_minor)

        # 7. Build window layout
        if window_specs:
            layout = self._build_custom_layout(
                window_specs, targets or [], services,
            )
        else:
            layout = self._build_default_layout(services)

        # 8. Launch
        print(f"Using Python: {python}")
        self._session.launch(
            SESSION_NAME, layout, commands, self._registry.log_dir,
        )

        if not fg:
            self._print_summary(services, infra)
            self._session.attach(SESSION_NAME)

    def shell(self, service_name: str) -> None:
        """Drop into an interactive shell with the service's context loaded."""
        svc = self._registry.get_service(service_name)
        _, python_minor = self._venv_svc.detect_python()
        context = self._build_context_command(svc, python_minor)
        shell_cmd = f"{context} && exec bash"
        print(f"\n🐚 Entering {svc.name} environment…\n")
        bash = resolve_bash()
        os.execvp(bash, [bash, "-c", shell_cmd])

    def exec_in_context(self, service_name: str, command: list[str]) -> int:
        """Run *command* inside the service's context and return its exit code."""
        svc = self._registry.get_service(service_name)
        _, python_minor = self._venv_svc.detect_python()
        context = self._build_context_command(svc, python_minor)
        user_cmd = shlex.join(command)
        shell_cmd = f"{context} && {user_cmd}"
        bash = resolve_bash()
        return subprocess.run([bash, "-c", shell_cmd]).returncode

    # -- private helpers -----------------------------------------------------

    @staticmethod
    def _validate_start(services: list[ServiceInfo], *, fg: bool) -> None:
        non_primary = [s for s in services if not s.is_primary]
        primary = [s for s in services if s.is_primary]

        if not primary and non_primary:
            names = ", ".join(s.name for s in non_primary)
            raise RuntimeError(
                f"Cannot start only non-primary services ({names}).\n"
                f"   Non-primary services (workers) must be launched alongside "
                f"their parent service.\n"
                f"   Try a group like 'rag-stack' or 'agents' instead."
            )

        if fg:
            if len(services) != 1:
                raise RuntimeError(
                    f"Foreground mode (--fg) requires exactly one service, "
                    f"got {len(services)}."
                )
            if not services[0].is_primary:
                raise RuntimeError(
                    f"Cannot run non-primary service '{services[0].name}' "
                    f"in foreground mode."
                )

    def _build_context_command(self, svc: ServiceInfo, python_minor: str) -> str:
        """Build the cd + venv-activate + env-source prefix for a service."""
        parts: list[str] = []
        svc_dir = self._root / svc.directory
        parts.append(f"cd {shlex.quote(str(svc_dir))}")

        if svc.type is ServiceType.PYTHON:
            parts.append("source venv/bin/activate")

        if svc.env_file:
            parts.append(f"set -a && source {shlex.quote(svc.env_file)} 2>/dev/null; set +a")

        return " && ".join(parts)

    def _build_commands(
        self, services: list[ServiceInfo], python_minor: str,
    ) -> dict[str, str]:
        """Build the full shell command for each service."""
        commands: dict[str, str] = {}
        for svc in services:
            context = self._build_context_command(svc, python_minor)
            launch = svc.launch
            if svc.type is ServiceType.PYTHON:
                launch = launch.replace("python ", f"python{python_minor} ")
                launch = f"PYTHONUNBUFFERED=1 {launch}"
            commands[svc.name] = f"{context} && {launch}"
        return commands

    @staticmethod
    def _build_default_layout(services: list[ServiceInfo]) -> list[WindowLayout]:
        """Primary services in a 'services' window, workers in a 'workers' window."""
        primary = [s for s in services if s.is_primary]
        workers = [s for s in services if not s.is_primary]
        layout: list[WindowLayout] = []
        if primary:
            layout.append(WindowLayout(name="services", services=primary))
        if workers:
            layout.append(WindowLayout(name="workers", services=workers))
        return layout

    def _build_custom_layout(
        self,
        window_specs: list[tuple[str | None, list[str]]],
        bare_targets: list[str],
        all_services: list[ServiceInfo],
    ) -> list[WindowLayout]:
        """Build layout from explicit --window specs and bare positional targets."""
        by_name = {s.name: s for s in all_services}
        assigned: set[str] = set()
        layout: list[WindowLayout] = []

        if bare_targets:
            bare_svcs = self._registry.resolve_services(bare_targets)
            layout.append(WindowLayout(name="services", services=bare_svcs))
            assigned.update(s.name for s in bare_svcs)

        for i, (win_name, names) in enumerate(window_specs):
            svcs = [
                by_name[s.name]
                for s in self._registry.resolve_services(names)
                if s.name in by_name and s.name not in assigned
            ]
            if not svcs:
                continue
            if win_name is None:
                win_name = svcs[0].name if len(svcs) == 1 else f"window-{i}"
            layout.append(WindowLayout(name=win_name, services=svcs))
            assigned.update(s.name for s in svcs)

        remaining = [s for s in all_services if s.name not in assigned]
        if remaining:
            layout.append(WindowLayout(name="services", services=remaining))

        return layout

    def _check_ports(self, services: list[ServiceInfo]) -> list[str]:
        """Check service ports for conflicts and offer to kill occupants."""
        occupied: list[tuple[ServiceInfo, list[PortOccupant]]] = []

        for svc in services:
            if not svc.port:
                continue
            occupants = self._process.find_port_occupants(svc.port)
            if occupants:
                occupied.append((svc, occupants))
                procs = ", ".join(
                    f"{o.name} (PID {o.pid})" for o in occupants
                )
                print(f"  ⚠ port {svc.port} ({svc.name}) — in use by: {procs}")
            else:
                print(f"  ✔ port {svc.port} ({svc.name}) — free")

        if not occupied:
            return []

        try:
            answer = input(
                "\n  Kill processes on occupied ports? [y/N]: "
            ).strip().lower()
        except EOFError:
            answer = ""

        if answer not in ("y", "yes"):
            return [svc.name for svc, _ in occupied]

        all_pids = [o.pid for _, occupants in occupied for o in occupants]
        self._process.kill_processes(all_pids)

        for svc, occupants in occupied:
            pid_str = ", ".join(str(o.pid) for o in occupants)
            print(f"  ✔ Killed processes on port {svc.port} (PIDs: {pid_str})")
        return []

    def _print_summary(
        self, services: list[ServiceInfo], infra: list[InfraComponent],
    ) -> None:
        print()
        print("╔══════════════════════════════════════════════════════════════╗")
        print("║              UnifAI Development Environment                 ║")
        print("╠══════════════════════════════════════════════════════════════╣")
        print(f"║  Session: {SESSION_NAME:<49}║")
        print("║                                                             ║")
        if infra:
            print("║  Infrastructure:                                            ║")
            for comp in infra:
                port_str = ", ".join(
                    p.split(":")[0] for p in comp.ports
                )
                line = f"    {comp.label:<20} (port {port_str})"
                print(f"║  {line:<57}║")
            print("║                                                             ║")
        primary = [s for s in services if s.is_primary]
        workers = [s for s in services if not s.is_primary]
        if primary:
            print("║  Services:                                                  ║")
            for svc in primary:
                port_info = f"port {svc.port}" if svc.port else ""
                line = f"    {svc.name:<20} ({port_info})"
                print(f"║  {line:<57}║")
        if workers:
            print("║  Workers:                                                   ║")
            for svc in workers:
                print(f"║    {svc.name:<55}║")
        print("║                                                             ║")
        print(f"║  Attach:  tmux attach -t {SESSION_NAME:<34}║")
        print(f"║  Destroy: unifai-dev destroy{' ':<31}║")
        groups = self._registry.group_names()
        if groups:
            group_str = ", ".join(groups)
            if len(group_str) > 49:
                group_str = group_str[:46] + "..."
            print(f"║  Groups:  {group_str:<49}║")
        print("║                                                             ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        print()
