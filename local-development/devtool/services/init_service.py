"""Application service: first-time setup wizard."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from devtool.domain.registry import Registry
from devtool.ports.container_runtime import ContainerRuntime
from devtool.services.env_service import EnvService
from devtool.services.infra_service import InfraService
from devtool.services.venv_service import VenvService


class InitService:

    def __init__(
        self,
        registry: Registry,
        root: Path,
        runtime: ContainerRuntime,
        infra_service: InfraService,
        venv_service: VenvService,
        env_service: EnvService,
    ) -> None:
        self._registry = registry
        self._root = root
        self._runtime = runtime
        self._infra_svc = infra_service
        self._venv_svc = venv_service
        self._env_svc = env_service

    def init(self, *, non_interactive: bool = False) -> None:
        """First-time setup: prerequisites, infra, venvs, env, patches."""
        print("🚀 UnifAI first-time setup\n")

        # 1. Prerequisites
        print("1/6  Checking prerequisites…")
        python, python_minor = self._venv_svc.detect_python()
        print(f"  ✔ Python: {python} ({python_minor})")

        print(f"  ✔ Container runtime: {self._runtime.runtime_name}")

        if not shutil.which("tmux"):
            print("  ✖ tmux not found — install tmux to use multi-service mode.")
        else:
            print("  ✔ tmux available")
        print()

        # 2. Infrastructure
        print("2/6  Starting infrastructure…")
        self._infra_svc.start()
        print()

        # 3. Venvs
        print("3/6  Setting up virtual environments…")
        existing_venvs = self._venv_svc.existing_venvs(
            self._registry.primary_services(),
        )
        if existing_venvs and not non_interactive:
            names = ", ".join(s.name for s in existing_venvs)
            print(f"  ℹ Existing venvs found: {names}")
            answer = input("  Recreate virtual environments? [y/N]: ").strip().lower()
            if answer in ("y", "yes"):
                self._venv_svc.setup(force=True)
            else:
                print("  ⏭ Skipping venv recreation.")
        else:
            self._venv_svc.setup()
        print()

        # 4. Env generation
        print("4/6  Generating .env files…")
        existing_envs = [
            svc for svc in self._registry.all_services()
            if svc.env_file
            and self._env_svc.env_file_exists(svc)
        ]
        if existing_envs and not non_interactive:
            names = ", ".join(s.name for s in existing_envs)
            print(f"  ℹ Existing .env files found: {names}")
            answer = input("  Regenerate .env files? [y/N]: ").strip().lower()
            if answer in ("y", "yes"):
                self._env_svc.get_or_create_shared_secret()
                self._env_svc.generate(force=True)
                self._env_svc.auto_resolve_generated_keys()
            else:
                print("  ⏭ Keeping existing .env files (checking for missing keys).")
                self._env_svc.generate()
        else:
            self._env_svc.generate()
        print()

        # 5. Auto-generate and placeholder prompts
        print("5/6  Resolving auto-generated and placeholder values…")
        self._env_svc.resolve_auto_generate_keys(non_interactive=non_interactive)
        self._env_svc.resolve_placeholders(non_interactive=non_interactive)
        print()

        # 6. Shell completion
        print("6/6  Shell completion…")
        self._install_shell_completion(non_interactive=non_interactive)
        print()

        print("╔══════════════════════════════════════════════════════════════╗")
        print("║  Setup complete!                                            ║")
        print("║                                                             ║")
        print("║  Next steps:                                                ║")
        print("║    unifai-dev start         Start all services              ║")
        print("║    unifai-dev doctor        Verify everything is healthy    ║")
        print("║    unifai-dev list          Show services, groups, infra    ║")
        print("╚══════════════════════════════════════════════════════════════╝")

    @staticmethod
    def _install_shell_completion(*, non_interactive: bool = False) -> None:
        """Offer to install Typer shell completion for unifai-dev."""
        try:
            import shellingham
            shell_name, _ = shellingham.detect_shell()
        except Exception:
            shell_name = os.environ.get("SHELL", "")
            shell_name = Path(shell_name).name if shell_name else ""

        if not shell_name:
            print("  ⏭ Could not detect shell — run 'unifai-dev --install-completion' manually.")
            return

        if non_interactive:
            print(f"  ℹ Run 'unifai-dev --install-completion {shell_name}' to enable tab completion.")
            return

        try:
            answer = input(
                f"  Install tab autocompletion for {shell_name}? [Y/n]: "
            ).strip().lower()
        except EOFError:
            answer = "n"

        if answer in ("n", "no"):
            print(f"  ⏭ Skipped. Run 'unifai-dev --install-completion' later.")
            return

        result = subprocess.run(
            ["unifai-dev", "--install-completion", shell_name],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"  ✔ Completion installed for {shell_name}. Restart your shell to activate.")
        else:
            print(f"  ⚠ Could not install completion automatically.")
            print(f"    Run 'unifai-dev --install-completion {shell_name}' manually.")
