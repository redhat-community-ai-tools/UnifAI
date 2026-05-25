"""Adapter: virtual-environment manager using python -m venv / npm."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from devtool.domain.models import ServiceInfo, ServiceType, VenvStrategy
from devtool.ports.venv_manager import VenvManager


class LocalVenvManager(VenvManager):
    """Creates and verifies venvs on the local filesystem."""

    @staticmethod
    def _venv_bin(svc_dir: Path, name: str) -> Path:
        """Return path to a binary inside the service's venv."""
        return svc_dir / "venv" / "bin" / name

    def create(
        self, service: ServiceInfo, python: str, root: Path,
        *, log_dir: Path | None = None, force: bool = False,
    ) -> None:
        svc_dir = root / service.directory
        strategy = service.venv.strategy
        log_file = (log_dir / f"{service.name}.log") if log_dir else None

        if strategy is VenvStrategy.NONE:
            return

        if not force and self.exists(service, root):
            return

        if force:
            venv_dir = svc_dir / ("node_modules" if strategy is VenvStrategy.NODE else "venv")
            if venv_dir.exists():
                shutil.rmtree(venv_dir)

        if strategy in (VenvStrategy.TOML, VenvStrategy.REQUIREMENTS):
            self._create_venv_dir(service, python, svc_dir, log_file)

        self._install_deps(service, python, root, svc_dir, log_file)

    def verify(self, service: ServiceInfo, python_minor: str, root: Path) -> None:
        svc_dir = root / service.directory

        if service.type is ServiceType.NODE:
            return

        if service.venv.strategy is VenvStrategy.NONE:
            return

        venv_python = self._venv_bin(svc_dir, "python")
        if not venv_python.exists():
            raise RuntimeError(
                f"No venv found for {service.name} at {svc_dir / 'venv'}/"
            )

        result = subprocess.run(
            [str(venv_python), "--version"],
            capture_output=True, text=True,
        )
        try:
            venv_ver = result.stdout.strip().split()[-1]
            venv_minor = ".".join(venv_ver.split(".")[:2])
        except IndexError:
            raise RuntimeError(
                f"Could not determine Python version for {service.name} "
                f"(unexpected output from {venv_python} --version)"
            )

        if venv_minor != python_minor:
            raise RuntimeError(
                f"Python version mismatch for {service.name}!\n"
                f"  Detected interpreter: {python_minor}\n"
                f"  Venv Python: {venv_python} ({venv_ver})\n"
                f"  Recreate with: unifai-dev venv setup {service.name}"
            )

    def exists(self, service: ServiceInfo, root: Path) -> bool:
        svc_dir = root / service.directory
        if service.type is ServiceType.NODE:
            return (svc_dir / "node_modules").exists()
        if service.venv.strategy is VenvStrategy.NONE:
            return True
        return self._venv_bin(svc_dir, "activate").exists()

    def sync(
        self, service: ServiceInfo, python: str, root: Path,
        *, log_dir: Path | None = None,
    ) -> None:
        svc_dir = root / service.directory
        log_file = (log_dir / f"{service.name}.log") if log_dir else None

        if service.venv.strategy is VenvStrategy.NONE:
            return

        if not self.exists(service, root):
            raise RuntimeError(
                f"No venv found for {service.name}. "
                f"Run 'unifai-dev venv setup {service.name}' first."
            )

        self._install_deps(service, python, root, svc_dir, log_file)

    # -- private helpers -----------------------------------------------------

    def _create_venv_dir(
        self, service: ServiceInfo, python: str, svc_dir: Path,
        log_file: Path | None,
    ) -> None:
        """Create the venv directory, validating that the expected manifest exists."""
        strategy = service.venv.strategy
        if strategy is VenvStrategy.TOML:
            if not (svc_dir / "pyproject.toml").exists():
                raise RuntimeError(
                    f"{service.name}: no pyproject.toml found in {svc_dir}"
                )
        elif strategy is VenvStrategy.REQUIREMENTS:
            if not (svc_dir / "requirements.txt").exists():
                raise RuntimeError(
                    f"{service.name}: no requirements.txt found in {svc_dir}"
                )
        self._run([python, "-m", "venv", "venv"], svc_dir, log_file)

    def _install_deps(
        self, service: ServiceInfo, python: str, root: Path,
        svc_dir: Path, log_file: Path | None,
    ) -> None:
        """Install/update dependencies into an existing venv."""
        strategy = service.venv.strategy

        if strategy is VenvStrategy.NONE:
            return
        if strategy is VenvStrategy.NODE:
            self._create_node(svc_dir, log_file)
            return
        if strategy is VenvStrategy.CUSTOM:
            self._create_custom(service, python, svc_dir, log_file)
            return

        pip = str(self._venv_bin(svc_dir, "pip"))
        global_utils_rel = os.path.relpath(root / "global_utils", svc_dir)
        if strategy is VenvStrategy.TOML:
            cmds: list[list[str]] = [
                [pip, "install", "-e", "."],
                [pip, "install", "-e", global_utils_rel],
            ]
        else:
            cmds = [
                [pip, "install", "-r", "requirements.txt"],
                [pip, "install", "-e", global_utils_rel],
            ]
        for cmd in cmds:
            self._run(cmd, svc_dir, log_file)

    def _create_custom(
        self, service: ServiceInfo, python: str, svc_dir: Path,
        log_file: Path | None,
    ) -> None:
        for cmd_template in service.venv.commands:
            cmd_str = cmd_template.replace("{python}", python)
            self._run(shlex.split(cmd_str), svc_dir, log_file)

    def _create_node(self, svc_dir: Path, log_file: Path | None) -> None:
        if shutil.which("pnpm"):
            self._run(["pnpm", "install"], svc_dir, log_file)
        elif shutil.which("npm"):
            self._run(["npm", "install"], svc_dir, log_file)
        else:
            raise RuntimeError("Neither pnpm nor npm found on PATH.")

    def _run(self, cmd: list[str], cwd: Path, log_file: Path | None) -> None:
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as f:
                result = subprocess.run(
                    cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT,
                )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Command failed: {' '.join(cmd)}\n"
                    f"  See log: {log_file}"
                )
        else:
            print(f"    $ {' '.join(cmd)}")
            subprocess.check_call(cmd, cwd=cwd)
