"""Built-in resource lifecycle: admin CRUD, schema exposure, and per-identity
configuration overlays.

Split out of ``ResourcesService`` (which had grown to own base CRUD,
validation, card building, *and* the entire built-in admin/overlay
lifecycle) so each service stays within a single responsibility. This is an
internal collaborator, not an independent public API: external callers
(Flask endpoints, ``BlueprintResolver``, tests) go through
``ResourcesService``, which composes this class and delegates its built-in
methods to it — the "Service as Public API" pattern is preserved at the
``ResourcesService`` facade.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from mas.core.identity import Identity
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.ref import RefWalker
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.resources.builtin_models import BuiltinUserConfig, identity_to_key
from mas.resources.errors import BuiltinConfigUnavailableError
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.catalog.element_registry import ElementRegistry

logger = logging.getLogger(__name__)


class BuiltinResourceService:
    """Admin lifecycle + per-identity overlays for built-in resources."""

    def __init__(
        self,
        resource_registry: ResourcesRegistry,
        element_registry: ElementRegistry,
        field_encryption: ResourceFieldEncryption,
        builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
    ) -> None:
        self._store = resource_registry
        self.element_registry = element_registry
        self._fields = field_encryption
        self._builtin_user_config_repo = builtin_user_config_repo

    # ---------- Listing / schema ----------

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Resource]:
        """Return all built-in resources (public and draft), for admin listing."""
        return self._store.find_all_builtins(category=category, resource_type=type)

    def get_builtin_schema(self, rid: str, *, is_admin: bool = False) -> dict:
        """Return the element JSON schema with readOnly annotations for a built-in resource.

        Reads ReadOnlyHint from the Pydantic schema to determine which fields
        are configurable. Non-configurable visible fields get ``read_only: true`` added.
        Draft built-ins are only accessible to admins.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if (
            resource.visibility != ResourceVisibility.PUBLIC
            and not is_admin
        ):
            raise KeyError(rid)

        schema = self.element_registry.get_schema_json(
            ResourceCategory(resource.category), resource.type
        )

        configurable_names, _ = self._fields.scan_schema_hints(resource.category, resource.type)

        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            if "hidden" in hints:
                continue
            if field_name not in configurable_names:
                hints["read_only"] = {"read_only": True}
                field_schema["hints"] = hints

        return schema

    # ---------- Per-identity overlays ----------

    def get_user_config(
        self,
        rid: str,
        identity: Identity,
    ) -> Dict[str, Any] | None:
        """Return the user's current overlay for a built-in resource, or None.

        Decrypts sensitive fields so the UI can display masked values.
        Only returns fields that are marked as user-configurable.
        Draft built-ins are not configurable by end users.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if resource.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        if not self._builtin_user_config_repo:
            return None

        key = identity_to_key(identity)
        user_config = self._builtin_user_config_repo.get(rid, key)
        if not user_config:
            return None

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        filtered = {k: v for k, v in user_config.fields.items() if k in configurable_keys}
        return self._fields.decrypt_config_fields(filtered, sensitive_keys)

    def configure_builtin(
        self,
        rid: str,
        identity: Identity,
        config: Dict[str, Any],
    ) -> Resource:
        """Save per-user/team configuration for a built-in resource.

        Allowed fields are determined by ReadOnlyHint annotations on the element schema.
        Draft built-ins are not configurable by end users.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if resource.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        if not configurable_keys:
            raise ValueError("No configurable fields defined for this element type")

        filtered = {k: v for k, v in config.items() if k in configurable_keys}
        if not filtered:
            raise ValueError("No valid configurable fields provided")

        if not self._builtin_user_config_repo:
            raise BuiltinConfigUnavailableError()

        encrypted = self._fields.encrypt_config_fields(filtered, sensitive_keys)

        key = identity_to_key(identity)
        existing = self._builtin_user_config_repo.get(rid, key)
        if existing:
            existing.fields.update(encrypted)
            self._builtin_user_config_repo.save(existing)
        else:
            user_config = BuiltinUserConfig(
                resource_id=rid,
                identity_key=key,
                fields=encrypted,
            )
            self._builtin_user_config_repo.save(user_config)

        logger.info("Built-in resource '%s' configured for %s", rid, key)
        return resource

    def resolve_overlay(self, resource: Resource, identity: Identity) -> Dict[str, Any]:
        """Resolve the effective config overlay for a built-in resource.

        Used by ``ResourcesService.resolve()`` to merge a caller's overlay
        into the resource's base config at runtime.

        Uses ReadOnlyHint from the Pydantic schema to identify configurable
        fields, then looks up the single overlay document keyed by
        ``identity_to_key(identity)`` — i.e. whichever identity the caller
        is currently operating as (their own user identity, or a team
        identity when acting in a team workspace). There is no separate
        user-over-team fallback chain: each identity has its own
        independent overlay. Decrypts sensitive fields before returning.

        Fields absent from the user config are not included — the caller will
        keep the resource's ``cfg_dict`` value for those.
        """
        if not self._builtin_user_config_repo:
            return {}

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        if not configurable_keys:
            return {}

        key = identity_to_key(identity)
        user_config = self._builtin_user_config_repo.get(resource.rid, key)
        if not user_config:
            return {}

        overlay = {k: v for k, v in user_config.fields.items() if k in configurable_keys}
        return self._fields.decrypt_config_fields(overlay, sensitive_keys)

    # ---------- Admin lifecycle ----------

    def duplicate_builtin(
        self,
        rid: str,
        identity: Identity,
        name: str,
        config_overrides: Dict[str, Any] = None,
    ) -> Resource:
        """Clone a built-in resource into a custom resource."""
        source = self._store.get(rid)
        if source.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if source.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        # cfg_dict may contain encrypted sensitive fields — decrypt before
        # merging overrides so the merge operates on plaintext, then
        # re-encrypt the merged result. Encrypting without decrypting first
        # would double-encrypt already-ciphertext values and corrupt them.
        merged_config = self._store.raw_config(rid)
        if config_overrides:
            merged_config.update(config_overrides)

        model_cls = self.element_registry.get_schema(
            ResourceCategory(source.category), source.type)
        cfg_model = model_cls(**merged_config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls,
            category=source.category, type_key=source.type,
        )

        doc = Resource(
            rid=uuid4().hex,
            identity=identity,
            category=source.category,
            type=source.type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
            ownership=ResourceOwnership.CUSTOM,
            parent_builtin_id=source.rid,
        )
        return self._store.create(doc)

    def create_builtin(
        self,
        *,
        identity: Identity,
        category: str,
        type: str,
        name: str,
        config: dict,
        available_to_all: bool = False,
    ) -> Resource:
        """Create a resource directly as built-in (admin only).

        The identity of the creating admin is preserved so that every
        built-in resource document is owned by the admin who created it,
        keeping the identity consistent across all documents in the
        resources collection.

        Configurable fields are determined by ReadOnlyHint annotations on the element schema.
        """
        cat_enum = ResourceCategory(category)
        if cat_enum in ResourceCategory.builtin_disabled_categories():
            raise ValueError(
                f"Category '{category}' is not supported for built-in resources"
            )

        model_cls = self.element_registry.get_schema(ResourceCategory(category), type)
        cfg_model = model_cls(**config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls, category=category, type_key=type
        )

        doc = Resource(
            identity=identity,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
            ownership=ResourceOwnership.BUILTIN,
            visibility=ResourceVisibility.PUBLIC if available_to_all else ResourceVisibility.DRAFT,
        )
        return self._store.create(doc)

    def promote(self, rid: str) -> Resource:
        """Make a resource a public built-in (admin only).

        Accepts a custom resource (promotes to builtin + public) or an
        existing draft built-in (sets visibility to public). The original
        identity is preserved so API-created resources keep their admin owner.
        """
        resource = self._store.get(rid)
        if resource.ownership not in (
            ResourceOwnership.CUSTOM,
            ResourceOwnership.BUILTIN,
        ):
            raise ValueError(
                f"Cannot promote resource with ownership '{resource.ownership}'"
            )
        cat_enum = ResourceCategory(resource.category)
        if cat_enum in ResourceCategory.builtin_disabled_categories():
            raise ValueError(
                f"Category '{resource.category}' is not supported for built-in resources"
            )
        resource.ownership = ResourceOwnership.BUILTIN
        resource.visibility = ResourceVisibility.PUBLIC
        return self._store.update(resource)

    def demote(self, rid: str) -> Resource:
        """Demote a public built-in to draft (admin-only visibility)."""
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        resource.visibility = ResourceVisibility.DRAFT
        return self._store.update(resource)

    def update_builtin(
        self,
        rid: str,
        *,
        config: dict = None,
        name: str = None,
        available_to_all: bool = None,
    ) -> Resource:
        """Update a built-in resource (admin only).

        Allows updating config, name, and visibility.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")

        if config is not None:
            model_cls = self.element_registry.get_schema(
                ResourceCategory(resource.category), resource.type)
            cfg_model = model_cls(**config)
            resource.cfg_dict = self._fields.encrypt_fields(
                cfg_model.model_dump(mode="json"), model_cls,
                category=resource.category, type_key=resource.type,
            )
            resource.nested_refs = list(RefWalker.external_rids(cfg_model))

        if name is not None:
            resource.name = name

        if available_to_all is not None:
            resource.visibility = (
                ResourceVisibility.PUBLIC if available_to_all
                else ResourceVisibility.DRAFT
            )

        return self._store.update(resource)

    def toggle_visibility(self, rid: str, *, available_to_all: bool) -> Resource:
        """Set visibility of a built-in resource (admin only)."""
        if available_to_all:
            return self.promote(rid)
        return self.demote(rid)
