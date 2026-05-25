"""Application service: .env file orchestration."""

from __future__ import annotations

import secrets

from devtool.domain.env import (
    AUTOGEN_RE,
    ENV_HEADER,
    KEYCLOAK_KEYS,
    LOCAL_AUTH_SERVICE,
    PLACEHOLDER_RE,
    GenerateResult,
    expected_keys,
)
from devtool.domain.models import ServiceInfo
from devtool.domain.registry import Registry
from devtool.ports.env_file_store import EnvFileStore


class EnvService:

    def __init__(self, registry: Registry, store: EnvFileStore) -> None:
        self._registry = registry
        self._store = store

    # -- public API ----------------------------------------------------------

    def generate(self, *, force: bool = False) -> None:
        """Generate .env files for all services that need one."""
        print("🔧 Generating .env files…")
        generated: list[str] = []
        skipped: list[str] = []
        updated: list[str] = []
        warnings: list[str] = []

        for svc in self._registry.all_services():
            if not svc.env_entries or not svc.env_file:
                continue
            rel = str(svc.directory / svc.env_file)
            result = self._generate_single(svc, force=force)
            if result is GenerateResult.CREATED:
                print(f"  ✔ Generated {rel}")
                generated.append(rel)
            elif result is GenerateResult.UPDATED:
                print(f"  ✔ Updated {rel} (added missing keys)")
                updated.append(rel)
            else:
                print(f"  ⏭ Skipped {rel} (already exists)")
                skipped.append(rel)

            if self._align_local_auth(svc):
                if rel not in updated:
                    print(f"  ✔ Updated {rel} (aligned local_auth_enabled)")
                    updated.append(rel)

            placeholders, _ = self._check_unresolved(svc)
            for key in placeholders:
                warnings.append(
                    f"  ⚠ {svc.name}: {rel}  {key} is still a placeholder!"
                )

        if generated:
            print(f"\nGenerated: {', '.join(generated)}")
        if updated:
            print(f"\nUpdated (added missing keys): {', '.join(updated)}")
        if skipped:
            print(
                f"\nPreserved existing (use --force to regenerate): "
                f"{', '.join(skipped)}"
            )
        for w in warnings:
            print(w)

    def show(self, service_name: str) -> None:
        """Print the current .env config for a service."""
        svc = self._registry.get_service(service_name)
        if not svc.env_file:
            print(f"{svc.name}: no env file configured.")
            return

        raw = self._store.read_raw(svc)
        if raw is not None:
            env_path = svc.directory / svc.env_file
            print(f"── {env_path} ──")
            print(raw, end="")
        else:
            env_path = svc.directory / svc.env_file
            print(f"{env_path} does not exist yet.")
            if svc.env_entries:
                print("Template values:")
                for k, v in svc.env_entries.items():
                    print(f"  {k}={v}")

    def auto_resolve_generated_keys(self) -> None:
        """Silently resolve any ``<AUTO_GENERATE>`` markers left in .env files."""
        grouped = self._collect_auto_generate_keys()
        if not grouped:
            return

        by_name = {s.name: s for s in self._registry.all_services()}
        value = self._get_or_create_shared_secret()

        for key, svc_names in grouped.items():
            services = [by_name[n] for n in svc_names if n in by_name]
            count = self._resolve_auto_generate_key(key, value, services)
            print(f"  🔑 Auto-generated {key} for {count} service(s)")

    def resolve_auto_generate_keys(self, *, non_interactive: bool = False) -> None:
        """Prompt (or auto-resolve) ``<AUTO_GENERATE>`` env entries."""
        grouped = self._collect_auto_generate_keys()
        if not grouped:
            return

        by_name = {s.name: s for s in self._registry.all_services()}

        for key, svc_names in grouped.items():
            affected = ", ".join(svc_names)
            services = [by_name[n] for n in svc_names if n in by_name]

            if non_interactive:
                value = self._get_or_create_shared_secret()
                count = self._resolve_auto_generate_key(key, value, services)
                print(f"  ✔ {key}: auto-generated and applied to {count} service(s)")
                continue

            print(f"\n  🔑 {key} (used by: {affected}):")
            print(f"    [1] Auto-generate a shared dev key (recommended)")
            print(f"    [2] Enter your own value")
            choice = input("  Choice [1]: ").strip() or "1"

            if choice == "2":
                value = input(f"  Enter value for {key}: ").strip()
                if not value:
                    print(f"    ⏭ {key} skipped")
                    continue
            else:
                value = self._get_or_create_shared_secret()

            count = self._resolve_auto_generate_key(key, value, services)
            print(f"    ✔ {key} applied to {count} service(s)")

    def resolve_placeholders(self, *, non_interactive: bool = False) -> None:
        """Prompt for ``<REPLACE...>`` placeholder values."""
        any_placeholders = False
        for svc in self._registry.all_services():
            placeholders, _ = self._check_unresolved(svc)
            if not placeholders:
                continue
            any_placeholders = True
            if non_interactive:
                for key in placeholders:
                    print(f"  ⚠ {svc.name}: {key} is still a placeholder")
            else:
                for key in placeholders:
                    value = input(f"  Enter value for {svc.name} / {key}: ").strip()
                    if value:
                        self._store.replace_value(svc, key, value)
                        print(f"    ✔ {key} updated")
                    else:
                        print(f"    ⏭ {key} skipped")
        if not any_placeholders:
            print("  ✔ No placeholders to fill.")

    def check_missing_keys(
        self, service: ServiceInfo, *, local_auth: bool | None = None,
    ) -> set[str]:
        """Return env-entry keys expected but absent from the on-disk file."""
        if not service.env_file or not service.env_entries:
            return set()
        if not self._store.exists(service):
            return set()

        if local_auth is None:
            local_auth = self._registry.local_auth

        exp = expected_keys(service, local_auth=local_auth)
        on_disk = set(self._store.read_entries(service).keys())
        return exp - on_disk

    def check_unresolved(
        self, service: ServiceInfo,
    ) -> tuple[set[str], set[str]]:
        """Return ``(placeholders, auto_generate)`` keys still unresolved on disk."""
        return self._check_unresolved(service)

    def check_placeholders(self, service: ServiceInfo) -> set[str]:
        """Return env-entry keys whose ``<REPLACE...>`` marker is still on disk."""
        placeholders, _ = self._check_unresolved(service)
        return placeholders

    def check_auto_generate(self, service: ServiceInfo) -> set[str]:
        """Return env-entry keys whose ``<AUTO_GENERATE>`` marker is still on disk."""
        _, auto_gen = self._check_unresolved(service)
        return auto_gen

    def env_file_exists(self, service: ServiceInfo) -> bool:
        """Check whether a service's .env file exists on disk."""
        return self._store.exists(service)

    def get_or_create_shared_secret(self) -> str:
        """Public access to the shared secret (used by InitService)."""
        return self._get_or_create_shared_secret()

    # -- private business logic ----------------------------------------------

    def _generate_single(
        self, service: ServiceInfo, *, force: bool = False,
    ) -> GenerateResult:
        """Write or update the .env file for a single service."""
        if not service.env_entries or not service.env_file:
            return GenerateResult.SKIPPED

        local_auth = self._registry.local_auth

        if self._store.exists(service) and not force:
            missing = self._check_missing_keys(service, local_auth=local_auth)
            if not missing:
                return GenerateResult.SKIPPED
            new_lines: list[str] = []
            for key in missing:
                if key == "local_auth_enabled":
                    new_lines.append("local_auth_enabled=true\n")
                else:
                    new_lines.append(f"{key}={service.env_entries[key]}\n")
            self._store.append_lines(service, new_lines)
            return GenerateResult.UPDATED

        is_identity_local = local_auth and service.name == LOCAL_AUTH_SERVICE

        lines = [ENV_HEADER]
        for key, value in service.env_entries.items():
            if is_identity_local and key in KEYCLOAK_KEYS:
                continue
            lines.append(f"{key}={value}\n")

        if is_identity_local:
            lines.append("local_auth_enabled=true\n")

        self._store.write(service, "".join(lines))
        return GenerateResult.CREATED

    def _check_missing_keys(
        self, service: ServiceInfo, *, local_auth: bool,
    ) -> set[str]:
        """Return env-entry keys expected but absent from the on-disk file."""
        if not service.env_file or not service.env_entries:
            return set()
        if not self._store.exists(service):
            return set()

        exp = expected_keys(service, local_auth=local_auth)
        on_disk = set(self._store.read_entries(service).keys())
        return exp - on_disk

    def _check_unresolved(
        self, service: ServiceInfo,
    ) -> tuple[set[str], set[str]]:
        """Return ``(placeholders, auto_generate)`` keys still unresolved on disk."""
        empty: tuple[set[str], set[str]] = (set(), set())
        if not service.env_file or not service.env_entries:
            return empty

        placeholder_suspects = {
            key
            for key, value in service.env_entries.items()
            if PLACEHOLDER_RE.search(value)
        }
        autogen_suspects = {
            key
            for key, value in service.env_entries.items()
            if AUTOGEN_RE.search(value)
        }
        all_suspects = placeholder_suspects | autogen_suspects
        if not all_suspects:
            return empty

        if not self._store.exists(service):
            return empty

        on_disk = self._store.read_entries(service)

        placeholders: set[str] = set()
        auto_gen: set[str] = set()

        for key in all_suspects:
            if key not in on_disk:
                continue
            value_start = on_disk[key][:20]
            if key in placeholder_suspects and PLACEHOLDER_RE.search(value_start):
                placeholders.add(key)
            if key in autogen_suspects and AUTOGEN_RE.search(value_start):
                auto_gen.add(key)

        return placeholders, auto_gen

    def _collect_auto_generate_keys(self) -> dict[str, list[str]]:
        """Return ``{key: [service_names...]}`` for all unresolved auto-generate entries."""
        grouped: dict[str, list[str]] = {}
        for svc in self._registry.all_services():
            _, auto_gen = self._check_unresolved(svc)
            for key in auto_gen:
                grouped.setdefault(key, []).append(svc.name)
        return grouped

    def _align_local_auth(self, service: ServiceInfo) -> bool:
        """Ensure identity's ``local_auth_enabled`` line matches the registry flag.

        Returns True if the file was modified.
        """
        if service.name != LOCAL_AUTH_SERVICE or not service.env_file:
            return False
        if not self._store.exists(service):
            return False

        local_auth = self._registry.local_auth
        on_disk = self._store.read_entries(service)
        has_key = "local_auth_enabled" in on_disk

        if local_auth and not has_key:
            self._store.append_lines(service, ["local_auth_enabled=true\n"])
            return True

        if not local_auth and has_key:
            raw = self._store.read_raw(service)
            if raw is None:
                return False
            filtered = [
                line
                for line in raw.splitlines(keepends=True)
                if not line.lstrip().startswith("local_auth_enabled=")
            ]
            self._store.write(service, "".join(filtered))
            return True

        return False

    def _resolve_auto_generate_key(
        self, key: str, value: str, services: list[ServiceInfo],
    ) -> int:
        """Write *value* for *key* into every service's on-disk .env file."""
        updated = 0
        for svc in services:
            if not svc.env_file:
                continue
            if not self._store.exists(svc):
                continue
            self._store.replace_value(svc, key, value)
            updated += 1
        return updated

    def _get_or_create_shared_secret(self) -> str:
        """Return the shared dev secret, creating it on first call."""
        existing = self._store.read_shared_secret()
        if existing:
            return existing
        key = secrets.token_hex(32)
        self._store.write_shared_secret(key)
        return key
