"""Driving adapter: CLI that parses args and dispatches to the orchestrator."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import typer

if TYPE_CHECKING:
    from devtool.domain.registry import Registry
    from devtool.services.orchestrator import Orchestrator

# -- Root app ----------------------------------------------------------------

app = typer.Typer(
    name="unifai-dev",
    help=(
        "UnifAI local development tool.\n\n"
        "Quick start:\n"
        "  unifai-dev init              First-time setup (infra + venvs + .env)\n"
        "  unifai-dev start             Start all services in tmux\n"
        "  unifai-dev status            Health dashboard\n"
        "  unifai-dev doctor            Full diagnostic\n\n"
        "Discovery:\n"
        "  unifai-dev list              Show all services, groups, and infra\n"
        "  unifai-dev info <service>    Deep-dive into a single service\n\n"
        "Tip: run 'unifai-dev --install-completion' for tab autocompletion."
    ),
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

# -- Sub-apps ----------------------------------------------------------------

infra_app = typer.Typer(
    name="infra",
    help="Manage infrastructure containers",
    no_args_is_help=True,
)
app.add_typer(infra_app)

venv_app = typer.Typer(
    name="venv",
    help="Manage virtual environments",
    no_args_is_help=True,
)
app.add_typer(venv_app)

env_app = typer.Typer(
    name="env",
    help="Manage .env files",
    no_args_is_help=True,
)
app.add_typer(env_app)


# -- Tab-completion callbacks ------------------------------------------------


def _complete_targets(incomplete: str) -> list[str]:
    """Complete service and group names."""
    try:
        from devtool.adapters.registry_loader import YamlRegistryLoader
        r = YamlRegistryLoader.load()
        return [n for n in r.service_names() + r.group_names()
                if n.startswith(incomplete)]
    except Exception:
        return []


def _complete_services(incomplete: str) -> list[str]:
    """Complete service names only."""
    try:
        from devtool.adapters.registry_loader import YamlRegistryLoader
        r = YamlRegistryLoader.load()
        return [n for n in r.service_names() if n.startswith(incomplete)]
    except Exception:
        return []


def _complete_infra(incomplete: str) -> list[str]:
    """Complete infrastructure component names."""
    try:
        from devtool.adapters.registry_loader import YamlRegistryLoader
        r = YamlRegistryLoader.load()
        return [n for n in r.infra_names() if n.startswith(incomplete)]
    except Exception:
        return []


# -- Helpers -----------------------------------------------------------------

def _parse_window_specs(
    raw: list[str] | None,
) -> list[tuple[str | None, list[str]]] | None:
    """Parse --window values into ``[(name_or_None, [svc_names]), ...]``."""
    if not raw:
        return None
    specs: list[tuple[str | None, list[str]]] = []
    for entry in raw:
        if "=" in entry:
            name, rest = entry.split("=", 1)
            names = [n.strip() for n in rest.split(",") if n.strip()]
            specs.append((name.strip(), names))
        else:
            names = [n.strip() for n in entry.split(",") if n.strip()]
            specs.append((None, names))
    return specs


def _resolve_root() -> Path:
    """Find the repo root (parent of local-development/)."""
    script_dir = Path(__file__).resolve().parent.parent
    root = script_dir.parent
    if (root / "rag").is_dir() and (root / "ui").is_dir():
        return root

    alt = os.environ.get("UNIFAI_ROOT", "").strip()
    if alt:
        root = Path(alt).expanduser().resolve()
        if (root / "rag").is_dir() and (root / "ui").is_dir():
            return root
        print(
            f"❌ UNIFAI_ROOT='{alt}' does not contain expected "
            f"repo structure (missing rag/ or ui/).",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(
        f"❌ Cannot find UnifAI repo structure at {root}.\n"
        f"   Set UNIFAI_ROOT or run from the repo root.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def _load_registry() -> Registry:
    """Load the Registry without wiring adapters.

    Used by read-only commands (list, info) that only need the YAML data
    and should work even when Docker/tmux are unavailable.
    """
    from devtool.adapters.registry_loader import YamlRegistryLoader
    return YamlRegistryLoader.load()


def _create_orchestrator(*, fg: bool = False) -> Orchestrator:
    """Wire up adapters and return an Orchestrator."""
    from devtool.adapters.container import ContainerRuntimeFactory
    from devtool.adapters.foreground import ForegroundSessionManager
    from devtool.adapters.health_probe import NetworkHealthProbe
    from devtool.adapters.process import LocalProcessManager
    from devtool.adapters.python_detector import LocalPythonResolver
    from devtool.adapters.registry_loader import YamlRegistryLoader
    from devtool.adapters.tmux import TmuxSessionManager
    from devtool.adapters.venv import LocalVenvManager
    from devtool.services.diagnostic_service import DiagnosticService
    from devtool.services.env_service import EnvService
    from devtool.services.health_checker import HealthChecker
    from devtool.services.infra_service import InfraService
    from devtool.services.init_service import InitService
    from devtool.services.orchestrator import Orchestrator
    from devtool.services.startup_service import StartupService
    from devtool.services.venv_service import VenvService

    import shutil

    root = _resolve_root()
    registry = YamlRegistryLoader.load()
    runtime = ContainerRuntimeFactory.create()

    if not fg and not shutil.which("tmux"):
        print(
            "❌ tmux is not installed. Use --fg for single-service mode, "
            "or install tmux for multi-service sessions.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    session = ForegroundSessionManager() if fg else TmuxSessionManager()
    venv_mgr = LocalVenvManager()
    process_mgr = LocalProcessManager()
    python_resolver = LocalPythonResolver()
    health_probe = NetworkHealthProbe()
    health = HealthChecker(health_probe)

    infra_svc = InfraService(registry, runtime)
    venv_svc = VenvService(registry, root, venv_mgr, python_resolver)
    env_svc = EnvService(registry, root)
    startup_svc = StartupService(
        registry, root, runtime, session,
        process_mgr, venv_svc, env_svc,
    )
    diag_svc = DiagnosticService(
        registry, root, runtime, session, process_mgr,
        health, infra_svc, venv_svc,
    )
    init_svc = InitService(
        registry, root, runtime,
        infra_svc, venv_svc, env_svc,
    )

    return Orchestrator(
        registry=registry,
        root=root,
        container_runtime=runtime,
        session_manager=session,
        health_checker=health,
        startup_service=startup_svc,
        infra_service=infra_svc,
        venv_service=venv_svc,
        env_service=env_svc,
        diagnostic_service=diag_svc,
        init_service=init_svc,
    )


# -- Top-level commands ------------------------------------------------------

@app.command(
    epilog=(
        "Examples:\n"
        "  unifai-dev start                          Start everything\n"
        "  unifai-dev start backend ui               Only backend + UI\n"
        "  unifai-dev start agents                   Start a group\n"
        "  unifai-dev start multi-agent --fg         Single service, foreground\n"
        "  unifai-dev start --setup-venv             Create venvs first\n"
        "  unifai-dev start --window ai=multi-agent,temporal-worker"
    ),
)
def start(
    targets: Optional[list[str]] = typer.Argument(
        None,
        help="Service and/or group names (default: all)",
        autocompletion=_complete_targets,
    ),
    fg: bool = typer.Option(False, "--fg", help="Foreground single service"),
    setup_venv: bool = typer.Option(False, "--setup-venv", help="Create venvs first"),
    window: Optional[list[str]] = typer.Option(
        None, "--window",
        help="Pull services into a separate tmux window (repeatable). "
             "Format: [name=]svc1,svc2,...  "
             "Without positional targets, starts all services.",
    ),
):
    """Start services (or groups) in a tmux session."""
    orch = _create_orchestrator(fg=fg)
    window_specs = _parse_window_specs(window)
    orch.start(
        targets=targets or None,
        fg=fg,
        setup_venv=setup_venv,
        window_specs=window_specs,
    )


@app.command(
    epilog=(
        "Examples:\n"
        "  unifai-dev shell backend          Enter backend environment\n"
        "  unifai-dev shell multi-agent      Enter multi-agent environment"
    ),
)
def shell(
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Open an interactive shell with a service's venv and env loaded."""
    orch = _create_orchestrator()
    orch.shell(service)


@app.command(
    "exec",
    context_settings={"allow_extra_args": True, "allow_interspersed_args": False},
    epilog=(
        "Examples:\n"
        "  unifai-dev exec backend python -m pytest tests/\n"
        "  unifai-dev exec rag pip list\n"
        "  unifai-dev exec multi-agent mas --help"
    ),
)
def exec_cmd(
    ctx: typer.Context,
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Run a command inside a service's context, then exit."""
    if not ctx.args:
        print("Usage: unifai-dev exec <service> <command...>")
        raise SystemExit(1)
    orch = _create_orchestrator()
    raise SystemExit(orch.exec_in_context(service, ctx.args))


@app.command()
def attach(
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Jump to a service's tmux pane."""
    orch = _create_orchestrator()
    orch.attach(service)


@app.command()
def stop():
    """Stop the tmux session (services keep infra running)."""
    orch = _create_orchestrator()
    orch.stop()


@app.command(
    epilog=(
        "Examples:\n"
        "  unifai-dev restart backend          Restart a single service\n"
        "  unifai-dev restart agents            Restart a group\n"
        "  unifai-dev restart --failed          Auto-restart all unhealthy services"
    ),
)
def restart(
    services: Optional[list[str]] = typer.Argument(
        None,
        help="Service and/or group names",
        autocompletion=_complete_targets,
    ),
    failed: bool = typer.Option(False, "--failed", help="Auto-restart all broken services"),
):
    """Dependency-aware restart of services or groups."""
    orch = _create_orchestrator()
    orch.restart(targets=services or None, failed=failed)


@app.command()
def status():
    """Show health dashboard for infrastructure and services."""
    orch = _create_orchestrator()
    orch.status()


@app.command(
    epilog=(
        "Examples:\n"
        "  unifai-dev logs backend              Full log output\n"
        "  unifai-dev logs backend -f           Tail in real time"
    ),
)
def logs(
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Tail the log"),
):
    """View a service's log file."""
    orch = _create_orchestrator()
    orch.logs(service, follow=follow)


@app.command()
def doctor():
    """Run full diagnostic (Python, venvs, infra, ports, env files)."""
    orch = _create_orchestrator()
    orch.doctor()


@app.command()
def init(
    non_interactive: bool = typer.Option(
        False, "--non-interactive",
        help="Skip interactive prompts (warn about placeholders instead)",
    ),
):
    """First-time setup: prerequisites, infra, venvs, env files."""
    orch = _create_orchestrator()
    orch.init(non_interactive=non_interactive)


@app.command(
    epilog=(
        "Examples:\n"
        "  unifai-dev clean                     Remove logs + stopped containers\n"
        "  unifai-dev clean --dry-run            Preview what would be removed\n"
        "  unifai-dev clean --logs               Only clean log files\n"
        "  unifai-dev clean --venvs              Only clean virtual environments\n"
        "  unifai-dev clean --containers         Only clean stopped containers"
    ),
)
def clean(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed"),
    logs: bool = typer.Option(False, "--logs", help="Only clean log files"),
    venvs: bool = typer.Option(False, "--venvs", help="Only clean virtual environments"),
    containers: bool = typer.Option(False, "--containers", help="Only clean stopped containers"),
):
    """Remove stale resources (logs, stopped containers, venvs)."""
    orch = _create_orchestrator()
    has_filter = logs or venvs or containers
    orch.clean(
        dry_run=dry_run,
        clean_logs=logs or not has_filter,
        clean_venvs=venvs,
        clean_containers=containers or not has_filter,
    )


@app.command()
def destroy():
    """Kill everything: stop services and tear down infrastructure."""
    orch = _create_orchestrator()
    orch.destroy()


# -- list / info (read-only, no Orchestrator) --------------------------------

@app.command("list")
def list_cmd():
    """Show all services, groups, and infrastructure."""
    registry = _load_registry()

    print("\nServices:")
    for svc in registry.all_services():
        port_str = f":{svc.port}" if svc.port else ""
        role = " (worker)" if not svc.is_primary else ""
        print(f"  {svc.name:<18} {svc.type.value:<8} {port_str:<8} {svc.directory}/{role}")

    print("\nGroups:")
    for name in registry.group_names():
        group = registry.get_group(name)
        members = ", ".join(group.services)
        print(f"  {name:<16} -> {members}")

    print("\nInfrastructure:")
    for comp in registry.all_infra():
        ports = ", ".join(f":{p.split(':')[0]}" for p in comp.ports)
        print(f"  {comp.name:<12} {comp.label:<12} {ports}")
    print()


@app.command()
def info(
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Show detailed information about a single service."""
    registry = _load_registry()
    svc = registry.get_service(service)
    groups = registry.groups_for_service(service)

    print(f"\n  Service:        {svc.name}")
    print(f"  Type:           {svc.type.value}")
    print(f"  Directory:      {svc.directory}/")
    if svc.port:
        host = svc.host or "127.0.0.1"
        print(f"  Port:           {svc.port} (host: {host})")
    if svc.health_endpoint:
        print(f"  Health:         {svc.health_endpoint}")
    print(f"  Launch:         {svc.launch}")
    if svc.infrastructure:
        print(f"  Infrastructure: {', '.join(svc.infrastructure)}")
    if groups:
        print(f"  Groups:         {', '.join(groups)}")
    strategy = svc.venv.strategy.value
    if svc.venv.commands:
        strategy += f" ({len(svc.venv.commands)} commands)"
    print(f"  Venv:           {strategy}")
    if svc.env_file:
        count = len(svc.env_entries)
        print(f"  Env file:       {svc.env_file} ({count} entries)")

    workers = [
        s.name for s in registry.all_services()
        if s.directory == svc.directory and not s.is_primary and s.name != svc.name
    ]
    if workers:
        print(f"  Workers:        {', '.join(workers)}")
    print()


# -- infra subcommands -------------------------------------------------------

@infra_app.command(
    "start",
    epilog=(
        "Examples:\n"
        "  unifai-dev infra start                    Start all containers\n"
        "  unifai-dev infra start mongo redis         Cherry-pick containers\n"
        "  unifai-dev infra start --for backend       Only what backend needs"
    ),
)
def infra_start(
    containers: Optional[list[str]] = typer.Argument(
        None, help="Container names",
        autocompletion=_complete_infra,
    ),
    for_service: Optional[str] = typer.Option(
        None, "--for", help="Only what a service needs",
    ),
):
    """Start infrastructure containers."""
    orch = _create_orchestrator()
    orch.infra_start(targets=containers or None, for_service=for_service)


@infra_app.command("stop")
def infra_stop():
    """Stop all infrastructure containers."""
    orch = _create_orchestrator()
    orch.infra_stop()


@infra_app.command("status")
def infra_status():
    """Show status of all infrastructure containers."""
    orch = _create_orchestrator()
    orch.infra_status()


@infra_app.command("logs")
def infra_logs(
    component: str = typer.Argument(
        ..., help="Infrastructure component name",
        autocompletion=_complete_infra,
    ),
    follow: bool = typer.Option(False, "--follow", "-f", help="Tail the log"),
):
    """View container logs."""
    orch = _create_orchestrator()
    orch.infra_logs(component, follow=follow)


@infra_app.command("reset")
def infra_reset(
    components: Optional[list[str]] = typer.Argument(
        None, help="Component names",
        autocompletion=_complete_infra,
    ),
):
    """Reset containers (stop, remove, recreate)."""
    orch = _create_orchestrator()
    orch.infra_reset(targets=components or None)


# -- venv subcommands --------------------------------------------------------

@venv_app.command("setup")
def venv_setup(
    service: Optional[str] = typer.Argument(
        None, help="Service name",
        autocompletion=_complete_services,
    ),
    force: bool = typer.Option(False, "--force", help="Delete and recreate existing venvs"),
):
    """Create virtual environment(s)."""
    orch = _create_orchestrator()
    orch.venv_setup(service_name=service, force=force)


@venv_app.command("sync")
def venv_sync(
    service: Optional[str] = typer.Argument(
        None, help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Update dependencies in existing venv(s) without recreating."""
    orch = _create_orchestrator()
    orch.venv_sync(service_name=service)


@venv_app.command("check")
def venv_check():
    """Verify Python versions match across all venvs."""
    orch = _create_orchestrator()
    errors = orch.venv_check()
    if errors:
        raise SystemExit(1)


# -- env subcommands ---------------------------------------------------------

@env_app.command("generate")
def env_generate(
    force: bool = typer.Option(False, "--force", help="Overwrite existing .env files"),
):
    """Create or regenerate .env files from services.yaml templates."""
    orch = _create_orchestrator()
    orch.env_generate(force=force)


@env_app.command("show")
def env_show(
    service: str = typer.Argument(
        ..., help="Service name",
        autocompletion=_complete_services,
    ),
):
    """Print the current env config for a service."""
    orch = _create_orchestrator()
    orch.env_show(service)


# -- Entry point -------------------------------------------------------------

def main():
    """CLI entry point with clean error handling."""
    if sys.platform == "win32":
        print(
            "❌ unifai-dev does not support Windows natively. "
            "Please use WSL2.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    try:
        app()
    except (KeyError, RuntimeError, FileNotFoundError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1)
