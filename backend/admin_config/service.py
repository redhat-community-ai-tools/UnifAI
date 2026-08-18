"""
AdminConfigService — application service for admin configuration.

Responsibilities:
  - GET: merge the static template with stored values from MongoDB.
  - PUT: validate and persist a section's values, then dispatch the
         on_update_action to downstream services via ActionDispatcher.
"""
import logging
from typing import Any, Dict, Optional, Tuple

from admin_config.models import (
    AdminConfigEntry,
    AdminConfigResponse,
    AdminConfigTemplate,
    CategoryValue,
    FieldValue,
    SectionValue,
)
from admin_config.repository.repository import AdminConfigRepository
from admin_config.action_dispatcher import ActionDispatcher

logger = logging.getLogger(__name__)


class AdminConfigService:

    def __init__(
        self,
        repository: AdminConfigRepository,
        template: AdminConfigTemplate,
        action_dispatcher: ActionDispatcher,
    ):
        self._repo = repository
        self._template = template
        self._dispatcher = action_dispatcher

    # ──────────────────── GET (template + stored values) ──────────────────

    def get_config(self) -> AdminConfigResponse:
        """Return the full template merged with persisted values."""
        categories = []
        for cat_def in self._template.categories:
            sections = []
            for sec_def in cat_def.sections:
                entry = self._repo.get(sec_def.key)
                stored = entry.value if entry else {}
                updated_at = entry.updated_at if entry else None

                fields = []
                for f in sec_def.fields:
                    fields.append(FieldValue(
                        key=f.key,
                        label=f.label,
                        field_type=f.field_type,
                        description=f.description,
                        default=f.default,
                        placeholder=f.placeholder,
                        value=stored.get(f.key, f.default),
                    ))

                sections.append(SectionValue(
                    key=sec_def.key,
                    title=sec_def.title,
                    description=sec_def.description,
                    fields=fields,
                    on_update_action=sec_def.on_update_action,
                    updated_at=updated_at,
                ))

            categories.append(CategoryValue(
                key=cat_def.key,
                title=cat_def.title,
                description=cat_def.description,
                sections=sections,
            ))

        return AdminConfigResponse(categories=categories)

    # ──────────────────── PUT (persist a section) ─────────────────────────

    def update_section(
        self,
        section_key: str,
        values: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Persist values for one section.

        Returns:
            (success, on_update_action) — the action identifier that
            downstream services may react to, or None.
        """
        section_def = self._find_section(section_key)
        if section_def is None:
            raise KeyError(f"Unknown section: {section_key}")

        valid_keys = {f.key for f in section_def.fields}
        filtered = {k: v for k, v in values.items() if k in valid_keys}

        entry = AdminConfigEntry(key=section_key, value=filtered)
        self._repo.set(entry)

        logger.info("Admin config section '%s' updated", section_key)

        try:
            self._dispatcher.dispatch(
                action=section_def.on_update_action,
                target=section_def.on_update_target,
                endpoint=section_def.on_update_endpoint,
            )
        except Exception:
            logger.exception(
                "Dispatch failed for section '%s' action '%s'; "
                "config was saved but side-effect did not execute",
                section_key, section_def.on_update_action,
            )

        return True, section_def.on_update_action

    # ──────────────────── access control ─────────────────────────────────

    def is_admin(self, username: str) -> bool:
        """Check if *username* is in the admin_usernames list."""
        section_def = self._find_section("admin_users")
        if section_def is None:
            return False

        entry = self._repo.get("admin_users")
        if entry and entry.value:
            admin_usernames = entry.value.get("admin_usernames", [])
        else:
            field_def = next(
                (f for f in section_def.fields if f.key == "admin_usernames"),
                None,
            )
            admin_usernames = field_def.default if field_def else []

        return username.lower() in [u.lower() for u in admin_usernames]

    # ──────────────────── helpers ─────────────────────────────────────────

    def _find_section(self, key: str):
        for cat in self._template.categories:
            for sec in cat.sections:
                if sec.key == key:
                    return sec
        return None
