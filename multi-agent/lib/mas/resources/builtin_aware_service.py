"""Decorator over ``CoreResourceService``.  Adds built-in policies.

Both ``CoreResourceService`` and ``BuiltinAwareResourceService`` implement
``ResourceServicePort``.  Consumers depend on the protocol, never on a
concrete class — they can't tell which implementation they received.
The container decides which to inject:

    core = CoreResourceService(...)
    service = BuiltinAwareResourceService(inner=core, ...)   # or just core

``__getattr__`` transparently delegates any attribute not explicitly
defined on the decorator to the wrapped ``CoreResourceService`` instance,
so methods like ``count``, ``group_count``, ``get_dict``, and internal
helpers (``_dependency_resolver``, ``_validate_and_get``, etc.) are
available without explicit one-liner delegations.

Methods that call other overridden methods (``validate_resource`` calls
``self.get_visible``, for example) are re-implemented on the decorator so
that ``self.get_visible()`` dispatches to *this* class's version (with the
draft-gate), not the inner's.  Pure-delegation methods whose bodies never
call an overridden method are covered by ``__getattr__``.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.element_meta import ElementConfigMeta
from mas.core.identity import Identity
from mas.core.ref import RefWalker
from mas.elements.common.card import ElementCard
from mas.elements.common.validator import ElementValidationResult
from mas.resources.builtin_models import identity_to_key
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceLockedError,
)
from mas.resources.models import Resource
from mas.resources.ports import AdminEditLockReader
from mas.resources.repository.builtin_resource_descriptor_repository import (
    BuiltinResourceDescriptorRepository,
)
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.resources.service import CoreResourceService

AUTH_METADATA_OVERLAY_FIELDS = frozenset({"server_identifier", "scheme_type"})

logger = logging.getLogger(__name__)


class BuiltinAwareResourceService:
    """Decorator over ``CoreResourceService``.  Adds built-in policies.

    Wraps a ``CoreResourceService`` instance and implements the same
    ``ResourceServicePort`` protocol.  Overrides 8 methods to layer draft
    visibility gating, overlay merging, write protection, admin edit-lock
    enforcement, descriptor cleanup, and ownership/visibility serialization
    on top of the pure CRUD core.

    If the built-in feature is removed, delete this class and have the
    container inject ``CoreResourceService`` directly — no other file
    changes required.
    """

    def __init__(
        self,
        inner: CoreResourceService,
        *,
        descriptor_repo: BuiltinResourceDescriptorRepository,
        builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
        admin_lock_reader: Optional[AdminEditLockReader] = None,
    ) -> None:
        self._inner = inner
        self._descriptors = descriptor_repo
        self._user_configs = builtin_user_config_repo
        self._admin_lock_reader = admin_lock_reader

    def __getattr__(self, name: str):
        """Delegate any attribute not found on the decorator to the inner service."""
        return getattr(self._inner, name)

    # ── Protocol-required delegations ────────────────────────────────────
    #
    # Explicit one-liners for every method that appears on a Protocol
    # consumers depend on (ResourceServicePort, ResourceClonePort,
    # ResourceReader) so that @runtime_checkable isinstance() checks pass
    # and static type-checkers see concrete definitions.
    #
    # Methods already overridden or re-implemented below are NOT repeated
    # here — only the pure pass-through ones.

    def create(self, *, identity: Identity, category, type, name, config) -> Resource:
        return self._inner.create(
            identity=identity, category=category, type=type, name=name, config=config,
        )

    def save_resource(self, resource: Resource) -> Resource:
        return self._inner.save_resource(resource)

    def update(self, rid: str, *, config: dict, name: str = None) -> Resource:
        return self._inner.update(rid, config=config, name=name)

    def get(self, rid: str) -> Resource:
        return self._inner.get(rid)

    def exists_by_name(
        self, identity: Identity, category: str, type_: str, name: str,
    ) -> bool:
        return self._inner.exists_by_name(identity, category, type_, name)

    # ── Overridden methods (add built-in policies) ───────────────────────

    def get_visible(
        self, rid: str, *, caller: CallerScope = CallerScope(),
    ) -> Resource:
        """Draft-gate + identity ownership check.

        Draft built-ins are only visible to admins.  Non-admin callers
        receive a ``KeyError`` (404) for draft built-ins.
        """
        resource = self._inner._store.get(rid)
        if caller.is_admin:
            return resource
        descriptor = self._descriptors.get(rid)
        if descriptor is not None and descriptor.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)
        if (
            caller.identity is not None
            and descriptor is None
            and (
                resource.identity.type != caller.identity.type
                or resource.identity.id != caller.identity.id
            )
        ):
            raise KeyError(rid)
        return resource

    def find_resources(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
        ownership: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        caller: CallerScope = CallerScope(),
    ) -> Tuple[List[dict], int]:
        """Merge user's resources + public built-ins."""
        category_enum = ResourceCategory(category) if category else None
        ownership_enum = ResourceOwnership(ownership) if ownership else None

        resources, total = self._descriptors.find_visible_for_identity(
            identity=caller.identity,
            category=category_enum.value if category_enum else None,
            resource_type=type,
            ownership=ownership_enum,
            is_admin=caller.is_admin,
            limit=limit,
            offset=offset,
            sort_by="created",
            sort_order="desc",
        )
        return self.to_dicts(resources, identity=caller.identity), total

    def resolve_resource(
        self, resource: Resource, caller: CallerScope = CallerScope(),
    ) -> BaseModel:
        """Resolve config, then merge built-in overlay if applicable."""
        config = self._inner._store.raw_config_for(resource)

        descriptor = self._descriptors.get(resource.rid)
        if descriptor is not None and caller.identity is not None:
            config = self._strip_and_merge_overlay(resource, config, caller.identity)

        model_cls = self._inner.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type)
        return model_cls(**config)

    def delete(self, rid: str) -> None:
        """Delete resource, then clean up descriptor + overlays."""
        self._inner.delete(rid)
        descriptor = self._descriptors.get(rid)
        if descriptor is not None:
            self._descriptors.delete(rid)
            if self._user_configs:
                self._user_configs.delete_all_for_resource(rid)

    def guard_write_access(
        self, rid: str, caller: CallerScope, *, username: str = "",
    ) -> Resource:
        """Built-in write protection + lock check, then ownership check."""
        resource = self._inner._store.get(rid)
        descriptor = self._descriptors.get(rid)
        is_builtin = descriptor is not None

        if caller.is_admin:
            if is_builtin:
                self._check_admin_edit_lock(rid, username)
            return resource

        if is_builtin:
            raise BuiltInWriteProtectedError()

        if (
            caller.identity is None
            or resource.identity.type != caller.identity.type
            or resource.identity.id != caller.identity.id
        ):
            raise ResourceAccessDeniedError(rid)
        return resource

    def to_dict(self, resource: Resource) -> dict:
        """Serialize, stamping ownership/visibility from descriptor."""
        data = resource.model_dump(mode="json")
        descriptor = self._descriptors.get(resource.rid)
        if descriptor is None:
            data["ownership"] = ResourceOwnership.CUSTOM.value
        else:
            data["ownership"] = ResourceOwnership.BUILTIN.value
            data["visibility"] = descriptor.visibility.value
        return data

    def to_dicts(
        self,
        resources: List[Resource],
        *,
        identity: Optional[Identity] = None,
    ) -> List[dict]:
        """Serialize resources, attaching ``user_configured`` for built-ins."""
        configured_rids: set = set()
        if identity is not None and self._user_configs:
            key = identity_to_key(identity)
            for cfg in self._user_configs.find_by_identity(key):
                configured_rids.add(cfg.resource_id)

        result = []
        for doc in resources:
            data = self.to_dict(doc)
            if data.get("ownership") == ResourceOwnership.BUILTIN.value:
                data["user_configured"] = doc.rid in configured_rids
            result.append(data)
        return result

    # ── Re-implemented methods (self-calls must route through decorator) ─
    #
    # These methods exist on CoreResourceService but call overridden methods
    # internally (get_visible, resolve_resource, _build_configs_from_rids).
    # Delegating to self._inner would bypass the decorator's overrides, so
    # they are re-implemented here with self.X() calls that route through
    # the decorator's versions.  Internal state is accessed via the inner.

    def resolve(
        self, rid: str, caller: CallerScope = CallerScope(),
    ) -> BaseModel:
        resource = self.get_visible(rid, caller=caller)
        return self.resolve_resource(resource, caller=caller)

    def validate_resource(
        self,
        rid: str,
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        self._inner._ensure_validation_service()
        self.get_visible(rid, caller=caller)
        ordered_rids = self._inner._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")
        ordered_configs = self._build_configs_from_rids(ordered_rids, caller=caller)
        return self._inner._validate_and_get(
            ordered_configs, rid, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_resources(
        self,
        rids: List[str],
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        max_workers: int = 10,
        credential_user_id: str = "",
    ) -> List[ElementValidationResult]:
        self._inner._ensure_validation_service()
        if not rids:
            return []
        if len(rids) == 1:
            return [
                self._validate_resource_safe(
                    rids[0], caller, user_id, timeout_seconds, credential_user_id,
                ),
            ]
        return self._validate_in_parallel(
            rids, caller, user_id, timeout_seconds, max_workers, credential_user_id,
        )

    def _validate_in_parallel(
        self,
        rids: List[str],
        caller: CallerScope,
        user_id: str,
        timeout_seconds: float,
        max_workers: int,
        credential_user_id: str = "",
    ) -> List[ElementValidationResult]:
        results: List[Optional[ElementValidationResult]] = [None] * len(rids)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    self._validate_resource_safe,
                    rid, caller, user_id, timeout_seconds, credential_user_id,
                ): idx
                for idx, rid in enumerate(rids)
            }
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()
        return results

    def _validate_resource_safe(
        self,
        rid: str,
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        try:
            return self.validate_resource(
                rid=rid, caller=caller, user_id=user_id,
                timeout_seconds=timeout_seconds,
                credential_user_id=credential_user_id,
            )
        except KeyError:
            return ElementValidationResult.create_error(
                rid=rid, error=f"Resource not found: {rid}",
            )
        except Exception as e:
            return ElementValidationResult.create_error(
                rid=rid, error=f"Validation failed: {str(e)}",
            )

    def validate_config(
        self,
        category: str,
        element_type: str,
        config: dict,
        name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> ElementValidationResult:
        self._inner._ensure_validation_service()
        category_enum = ResourceCategory(category)
        model_cls = self._inner.element_registry.get_schema(category_enum, element_type)
        cfg_model = model_cls(**config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        dep_rids = self._inner._dependency_resolver.resolve_all_with_deps(nested_refs)
        ordered_configs = self._build_configs_from_rids(dep_rids)
        ordered_configs.append(ElementConfigMeta(
            rid="inline",
            category=category_enum,
            type_key=element_type,
            name=name or "inline",
            config=cfg_model,
            dependency_rids=nested_refs,
        ))
        return self._inner._validate_and_get(ordered_configs, "inline", timeout_seconds)

    def get_cards(
        self,
        rids: List[str],
        caller: CallerScope = CallerScope(),
    ) -> Dict[str, ElementCard]:
        self._inner._ensure_card_service()
        for rid in rids:
            self.get_visible(rid, caller=caller)
        all_rids = self._inner._dependency_resolver.resolve_all_with_deps(rids)
        configs = self._build_configs_from_rids(all_rids, caller=caller)
        return self._inner._card_service.build_all_cards(configs)

    def get_card(
        self,
        rid: str,
        caller: CallerScope = CallerScope(),
    ) -> ElementCard:
        cards = self.get_cards([rid], caller=caller)
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

    # ── Overridden internal method ───────────────────────────────────────

    def _build_configs_from_rids(
        self, rids: List[str], caller: CallerScope = CallerScope(),
    ) -> List[ElementConfigMeta]:
        """Build ElementConfigMeta list, adding builtin validation-override
        checks for built-in resources.
        """
        configs: List[ElementConfigMeta] = []
        for rid in rids:
            resource = self.get_visible(rid, caller=caller)
            config = self.resolve_resource(resource, caller=caller)

            descriptor = self._descriptors.get(rid)
            if descriptor is not None:
                override_error = self._builtin_validation_override_error(
                    resource, config, caller.identity
                )
            else:
                override_error = None
                missing = self._inner._fields.find_missing_conditionally_required_secrets(
                    resource.category, resource.type, config
                )
                if missing:
                    override_error = (
                        f"{', '.join(missing)} is required for '{resource.name}' — "
                        f"set it in the resource's configuration before it can be validated."
                    )

            configs.append(ElementConfigMeta(
                rid=rid,
                category=resource.category,
                type_key=resource.type,
                name=resource.name,
                config=config,
                dependency_rids=list(resource.nested_refs),
                validation_override_error=override_error,
            ))
        return configs

    # ── Built-in overlay helpers ─────────────────────────────────────────

    def _auth_metadata_keys(self, resource: Resource) -> set:
        try:
            schema = self._inner.element_registry.get_schema_json(
                ResourceCategory(resource.category), resource.type
            )
        except KeyError:
            return set()
        return AUTH_METADATA_OVERLAY_FIELDS & schema.get("properties", {}).keys()

    def _strip_and_merge_overlay(
        self,
        resource: Resource,
        config: Dict[str, Any],
        identity: Identity,
    ) -> Dict[str, Any]:
        configurable_keys, sensitive_keys = self._inner._fields.scan_schema_hints(
            resource.category, resource.type
        )
        secret_configurable_keys = configurable_keys & sensitive_keys
        if secret_configurable_keys:
            config = dict(config)
            for key in secret_configurable_keys:
                config.pop(key, None)

        overlay = self._resolve_overlay(resource, identity, configurable_keys, sensitive_keys)
        if overlay:
            config = dict(config)
            config.update(overlay)
        return config

    def _resolve_overlay(
        self,
        resource: Resource,
        identity: Identity,
        configurable_keys: set,
        sensitive_keys: set,
    ) -> Dict[str, Any]:
        if not self._user_configs:
            return {}

        allowed_keys = configurable_keys | self._auth_metadata_keys(resource)
        if not allowed_keys:
            return {}

        key = identity_to_key(identity)
        user_config = self._user_configs.get(resource.rid, key)
        if not user_config:
            return {}

        model_cls = self._inner.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type
        )
        overlay = {k: v for k, v in user_config.fields.items() if k in allowed_keys}
        return self._inner._fields.decrypt_config_fields(overlay, sensitive_keys, model_cls)

    def _builtin_validation_override_error(
        self,
        resource: Resource,
        config: BaseModel,
        identity: Optional[Identity],
    ) -> Optional[str]:
        if identity is None:
            return None
        configurable_keys, sensitive_keys = self._inner._fields.scan_schema_hints(
            resource.category, resource.type
        )
        secret_configurable_keys = configurable_keys & sensitive_keys
        if not secret_configurable_keys:
            return None

        missing = self._inner._fields.find_missing_conditionally_required_secrets(
            resource.category,
            resource.type,
            config,
            candidate_keys=secret_configurable_keys,
            require_unconditional=True,
        )
        if not missing:
            return None
        return (
            f"Requires your own {', '.join(missing)} — configure it for "
            f"'{resource.name}' in your inventory before it can be validated."
        )

    def _check_admin_edit_lock(self, rid: str, username: str) -> None:
        if self._admin_lock_reader is None:
            return
        holder = self._admin_lock_reader.get_admin_edit_lock(rid)
        if holder is None:
            return
        if holder.user_id.casefold() == username.casefold():
            return
        raise ResourceLockedError(
            locked_by_user_id=holder.user_id,
            locked_by_display_name=holder.display_name,
        )
