"""Application service: virtual environment management."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from devtool.domain.models import ServiceInfo, ServiceType
from devtool.domain.registry import Registry
from devtool.ports.python_resolver import PythonResolver
from devtool.ports.venv_manager import VenvManager


class VenvService:

    def __init__(
        self,
        registry: Registry,
        root: Path,
        venv_manager: VenvManager,
        python_resolver: PythonResolver,
    ) -> None:
        self._registry = registry
        self._root = root
        self._venv = venv_manager
        self._python_resolver = python_resolver

    def detect_python(self) -> tuple[str, str]:
        """Returns (python_path, python_minor_str)."""
        py_min, py_max = self._registry.python_bounds()
        env_override = (os.environ.get("UNIFAI_PYTHON") or "").strip() or None
        return self._python_resolver.find_python(
            py_min, py_max, env_override=env_override,
        )

    # -- public: CLI-facing entrypoints --------------------------------------

    def setup(self, service_name: str | None = None, *, force: bool = False) -> None:
        python, _ = self.detect_python()
        targets = self._resolve_targets(service_name)
        log_dir = self._registry.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        skipped: list[str] = []

        def do_create(svc: ServiceInfo) -> str | None:
            existed = self._venv.exists(svc, self._root)
            self._venv.create(svc, python, self._root, log_dir=log_dir, force=force)
            if existed and not force:
                skipped.append(svc.name)
                return f"  ⏭ {svc.name} (already exists, use --force to recreate)"
            return None

        print(f"📦 Setting up virtual environments with {python}\n")
        errors = self._run_batch(
            targets, do_create,
            fail_label="Venv setup failed for",
            log_dir=log_dir,
        )
        if not errors and skipped:
            print("\n✅ Nothing to do (use --force to recreate).")
        elif not errors:
            print("\n✅ Virtual environment(s) created.")

    def sync(self, service_name: str | None = None) -> None:
        """Update dependencies in existing venvs without recreating them."""
        python, _ = self.detect_python()
        targets = self._resolve_targets(service_name)
        log_dir = self._registry.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        print(f"🔄 Syncing virtual environments with {python}\n")
        errors = self._run_batch(
            targets,
            lambda svc: self._venv.sync(svc, python, self._root, log_dir=log_dir),
            fail_label="Sync failed for",
            log_dir=log_dir,
        )
        if not errors:
            print("\n✅ Dependencies synced.")

    def check(self) -> list[str]:
        """Verify venvs. Returns list of failed service names."""
        _, python_minor = self.detect_python()
        python_svcs = [
            s for s in self._registry.primary_services()
            if s.type is ServiceType.PYTHON
        ]
        return self._run_batch(
            python_svcs,
            lambda svc: self._venv.verify(svc, python_minor, self._root),
            fail_label="Verification failed for",
        )

    # -- public: building blocks for other services --------------------------

    def setup_services(
        self, targets: list[ServiceInfo], python: str,
    ) -> list[str]:
        """Create venvs for pre-resolved targets. Returns failed service names."""
        log_dir = self._registry.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        return self._run_batch(
            targets,
            lambda svc: self._venv.create(svc, python, self._root, log_dir=log_dir),
            fail_label="Venv setup failed for",
            log_dir=log_dir,
        )

    def verify_services(
        self, targets: list[ServiceInfo], python_minor: str,
    ) -> None:
        """Verify venvs for pre-resolved targets. Raises on mismatch."""
        for svc in targets:
            self._venv.verify(svc, python_minor, self._root)

    def existing_venvs(self, targets: list[ServiceInfo]) -> list[ServiceInfo]:
        """Return the subset of *targets* that already have a venv."""
        return [svc for svc in targets if self._venv.exists(svc, self._root)]

    # -- private helpers -----------------------------------------------------

    def _resolve_targets(self, service_name: str | None) -> list[ServiceInfo]:
        if service_name:
            return [self._registry.get_service(service_name)]
        return self._registry.primary_services()

    def _run_batch(
        self,
        targets: list[ServiceInfo],
        action: Callable[[ServiceInfo], str | None],
        *,
        fail_label: str,
        log_dir: Path | None = None,
    ) -> list[str]:
        """Run *action* on each target, collect and report failures.

        *action* may return a custom success message; ``None`` uses the
        default ``✔`` line.
        """
        errors: list[str] = []
        for svc in targets:
            try:
                msg = action(svc)
                print(msg or f"  ✔ {svc.name}")
            except RuntimeError as exc:
                print(f"  ✖ {svc.name}: {exc}")
                errors.append(svc.name)
        if errors:
            print(f"\n⚠ {fail_label}: {', '.join(errors)}")
            if log_dir:
                print(f"  Check logs in {log_dir}/")
        return errors
