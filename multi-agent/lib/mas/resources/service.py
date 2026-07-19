import logging
from typing import List, Optional, Tuple, Dict, Any
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from global_utils.utils.crypto import FieldCipher
from mas.core.identity import Identity
from mas.resources.registry import ResourcesRegistry
from mas.catalog.element_registry import ElementRegistry
from mas.resources.models import Resource, ResourceQuery
from mas.resources.builtin_models import BuiltinUserConfig, identity_to_key
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.ref import RefWalker
from mas.core.dto import GroupedCount
from mas.core.element_meta import ElementConfigMeta
from mas.elements.common.validator import ElementValidationResult, ValidationContext
from mas.elements.common.card import ElementCard
from mas.catalog.card_service import ElementCardService
from mas.resources.resolver import DependencyResolver
from mas.resources.errors import BuiltInWriteProtectedError
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)

class ResourcesService:
    """
    Public facade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            builtin_user_config_repo: BuiltinUserConfigRepository = None,
            validation_service: ElementValidationService = None,
            card_service: ElementCardService = None,
            auth_service=None,
            encryption_key: str = "",
    ):
        self._store = resource_registry
        self.element_registry = element_registry
        self._builtin_user_config_repo = builtin_user_config_repo
        self._card_service = card_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)
        self._validation_service = validation_service
        self._auth_service = auth_service
        self._cipher = FieldCipher(encryption_key) if encryption_key else None

    # ---------- CRUD ----------
    def create(self, *, identity: Identity, category, type, name, config) -> Resource:
        model_cls = self.element_registry.get_schema(ResourceCategory(category), type)
        cfg_model = model_cls(**config)

        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._encrypt_fields(cfg_model.model_dump(mode="json"), model_cls)

        doc = Resource(
            identity=identity,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
        )
        return self._store.create(doc)

    def save_resource(self, resource: Resource) -> Resource:
        """
        Save a pre-built Resource directly.

        Use this when you already have a validated Resource object.
        Skips schema validation since the Resource is already built.
        """
        return self._store.create(resource)

    def update(self, rid: str, *, config: dict, name: str = None) -> Resource:
        doc = self._store.get(rid)
        old_server_id = doc.cfg_dict.get("server_identifier", "")

        model_cls = self.element_registry.get_schema(
            ResourceCategory(doc.category), doc.type)
        cfg_model = model_cls(**config)

        nested_refs = list(RefWalker.external_rids(cfg_model))

        doc.cfg_dict = self._encrypt_fields(cfg_model.model_dump(mode="json"), model_cls)
        doc.nested_refs = nested_refs

        if name is not None:
            doc.name = name

        result = self._store.update(doc)

        new_server_id = doc.cfg_dict.get("server_identifier", "")
        if old_server_id and old_server_id != new_server_id:
            self._cleanup_orphaned_credential(doc.identity, old_server_id)

        return result

    def delete(self, rid: str) -> None:
        doc = self._store.get(rid)
        self._store.delete(rid)
        if (
            doc.ownership == ResourceOwnership.BUILTIN
            and self._builtin_user_config_repo
        ):
            self._builtin_user_config_repo.delete_all_for_resource(rid)
        server_id = doc.cfg_dict.get("server_identifier", "")
        if server_id:
            self._cleanup_orphaned_credential(doc.identity, server_id)

    # ---------- READ ----------
    def get(self, rid: str) -> Resource:
        """Get a single resource by ID."""
        return self._store.get(rid)

    def find_resources(self, identity: Identity, category: Optional[str] = None,
                       type: Optional[str] = None, ownership: Optional[str] = None,
                       limit: int = 50, offset: int = 0) -> Tuple[List[dict], int]:
        """Find resources with optional filtering and pagination.

        Returns serialized resource dicts. Built-ins include a
        ``user_configured`` flag indicating whether the caller has an overlay.
        """
        category_enum = ResourceCategory(category) if category else None
        ownership_enum = ResourceOwnership(ownership) if ownership else None

        query = ResourceQuery(
            identity=identity,
            category=category_enum,
            type=type,
            ownership=ownership_enum,
            limit=limit,
            offset=offset,
        )
        resources, total = self._store.find_resources(query)
        return self._serialize_with_user_configured(resources, identity), total

    # ---------- resolve ----------
    def resolve(self, rid: str, identity: Identity = None) -> BaseModel:
        resource = self._store.get(rid)
        config = dict(resource.cfg_dict)

        if resource.ownership == ResourceOwnership.BUILTIN and identity:
            overlay = self._resolve_builtin_overlay(resource, identity)
            if overlay:
                config.update(overlay)

        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type)
        return model_cls(**config)

    def get_dict(self, rid: str) -> dict:
        """Raw JSON for UI."""
        return self._store.raw_config(rid)

    @staticmethod
    def get_resource_schema() -> dict:
        """Get the JSON schema for Resource model."""
        return Resource.model_json_schema()

    # ---------- Statistics ----------
    def count(self, identity: Identity, filter: Dict[str, Any] = None) -> int:
        return self._store.count(identity, filter)

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None,
    ) -> List[GroupedCount]:
        """
        Group resources by specified fields and return counts.
        Performs efficient server-side grouping via the registry.
        """
        return self._store.group_count(identity, group_by, filter)

    # ---------- Validation ----------
    def validate_resource(
        self,
        rid: str,
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """
        Validate a saved resource and all its transitive dependencies.
        """
        self._ensure_validation_service()

        ordered_rids = self._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")

        ordered_configs = self._build_configs_from_rids(ordered_rids)

        return self._validate_and_get(
            ordered_configs, rid, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_resources(
        self,
        rids: List[str],
        user_id: str = "",
        timeout_seconds: float = 10.0,
        max_workers: int = 10,
        credential_user_id: str = "",
    ) -> List[ElementValidationResult]:
        """
        Validate multiple resources in parallel.

        Uses a thread pool for concurrent validation while preserving
        the order of results to match the input order.
        """
        self._ensure_validation_service()

        if not rids:
            return []

        if len(rids) == 1:
            return [
                self._validate_resource_safe(
                    rids[0], user_id, timeout_seconds, credential_user_id,
                ),
            ]

        return self._validate_in_parallel(
            rids, user_id, timeout_seconds, max_workers, credential_user_id,
        )

    def _validate_in_parallel(
        self,
        rids: List[str],
        user_id: str,
        timeout_seconds: float,
        max_workers: int,
        credential_user_id: str = "",
    ) -> List[ElementValidationResult]:
        """Execute validations concurrently with order preservation."""
        results: List[Optional[ElementValidationResult]] = [None] * len(rids)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    self._validate_resource_safe,
                    rid, user_id, timeout_seconds, credential_user_id,
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
        user_id: str,
        timeout_seconds: float,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """Validate a single resource with exception handling."""
        try:
            return self.validate_resource(
                rid=rid,
                user_id=user_id,
                timeout_seconds=timeout_seconds,
                credential_user_id=credential_user_id,
            )
        except KeyError:
            return ElementValidationResult.create_error(
                rid=rid,
                error=f"Resource not found: {rid}"
            )
        except Exception as e:
            return ElementValidationResult.create_error(
                rid=rid,
                error=f"Validation failed: {str(e)}"
            )

    def validate_config(
        self,
        category: str,
        element_type: str,
        config: dict,
        name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> ElementValidationResult:
        """
        Validate an inline config before saving.

        This validates a resource config without requiring it to be saved first.
        Useful for UI validation before creating a resource.
        """
        self._ensure_validation_service()

        category_enum = ResourceCategory(category)
        model_cls = self.element_registry.get_schema(category_enum, element_type)
        cfg_model = model_cls(**config)

        nested_refs = list(RefWalker.external_rids(cfg_model))
        dep_rids = self._resolve_transitive_deps(nested_refs)

        ordered_configs = self._build_configs_from_rids(dep_rids)

        ordered_configs.append(ElementConfigMeta(
            rid="inline",
            category=category_enum,
            type_key=element_type,
            name=name or "inline",
            config=cfg_model,
            dependency_rids=nested_refs,
        ))

        return self._validate_and_get(ordered_configs, "inline", timeout_seconds)

    # ---------- Card Building ----------
    def get_cards(
        self,
        rids: List[str],
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a list of resources and their dependencies.

        Resolves all transitive dependencies and builds cards for all elements
        in dependency order.
        """
        self._ensure_card_service()

        all_rids = self._dependency_resolver.resolve_all_with_deps(rids)
        configs = self._build_configs_from_rids(all_rids)

        return self._card_service.build_all_cards(configs)

    def get_card(
        self,
        rid: str,
    ) -> ElementCard:
        """
        Get element card for a single resource.

        Resolves all transitive dependencies and builds cards,
        returning only the card for the requested resource.
        """
        cards = self.get_cards([rid])
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Resource]:
        """Return all built-in resources (public and draft), for admin listing."""
        return self._store.find_all_builtins(category=category, type=type)

    # ---------- Built-in Resource Operations ----------

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

        configurable_names = self._get_configurable_keys(resource.category, resource.type)

        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            if "hidden" in hints:
                continue
            if field_name not in configurable_names:
                hints["read_only"] = {"read_only": True}
                field_schema["hints"] = hints

        return schema

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

        configurable_keys = self._get_configurable_keys(resource.category, resource.type)
        filtered = {k: v for k, v in user_config.fields.items() if k in configurable_keys}

        sensitive_keys = self._get_sensitive_keys(resource.category, resource.type)
        return self._decrypt_config_fields(filtered, sensitive_keys)

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

        configurable_keys = self._get_configurable_keys(resource.category, resource.type)
        if not configurable_keys:
            raise ValueError("No configurable fields defined for this element type")

        filtered = {k: v for k, v in config.items() if k in configurable_keys}
        if not filtered:
            raise ValueError("No valid configurable fields provided")

        sensitive_keys = self._get_sensitive_keys(resource.category, resource.type)
        encrypted = self._encrypt_config_fields(filtered, sensitive_keys)

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

        merged_config = dict(source.cfg_dict)
        if config_overrides:
            merged_config.update(config_overrides)

        model_cls = self.element_registry.get_schema(
            ResourceCategory(source.category), source.type)
        cfg_model = model_cls(**merged_config)
        nested_refs = list(RefWalker.external_rids(cfg_model))

        doc = Resource(
            rid=uuid4().hex,
            identity=identity,
            category=source.category,
            type=source.type,
            name=name,
            cfg_dict=cfg_model.model_dump(mode="json"),
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

        doc = Resource(
            identity=identity,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_model.model_dump(mode="json"),
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
            resource.cfg_dict = cfg_model.model_dump(mode="json")
            resource.nested_refs = list(RefWalker.external_rids(cfg_model))

        if name is not None:
            resource.name = name

        if available_to_all is not None:
            resource.visibility = (
                ResourceVisibility.PUBLIC if available_to_all
                else ResourceVisibility.DRAFT
            )

        return self._store.update(resource)

    def guard_builtin_write(self, rid: str, is_admin: bool) -> None:
        """Raise BuiltInWriteProtectedError if resource is built-in and caller is not admin."""
        resource = self._store.get(rid)
        if resource.ownership == ResourceOwnership.BUILTIN and not is_admin:
            raise BuiltInWriteProtectedError()

    # ---------- Internal Helpers ----------

    def _cleanup_orphaned_credential(self, identity: Identity, server_id: str) -> None:
        """Delete the stored credential if no other resource uses the same server_identifier."""
        if not self._auth_service:
            return
        remaining = self._store.count_by_config_field(
            identity, "server_identifier", server_id,
        )
        if remaining == 0:
            self._auth_service.delete_credential(identity.id, server_id)

    # ---------- Helpers ----------
    def _serialize_with_user_configured(
        self,
        resources: List[Resource],
        identity: Identity,
    ) -> List[dict]:
        """Serialize resources and attach ``user_configured`` for built-ins."""
        configured_rids: set = set()
        if self._builtin_user_config_repo:
            key = identity_to_key(identity)
            for cfg in self._builtin_user_config_repo.find_by_identity(key):
                configured_rids.add(cfg.resource_id)

        result = []
        for doc in resources:
            data = doc.model_dump(mode="json")
            if doc.ownership == ResourceOwnership.BUILTIN:
                data["user_configured"] = doc.rid in configured_rids
            result.append(data)
        return result

    def _encrypt_fields(self, cfg_dict: dict, model_cls: type) -> dict:
        """Encrypt fields declared in the config's ENCRYPTED_FIELDS before storage."""
        if not self._cipher:
            return cfg_dict
        for field in getattr(model_cls, "ENCRYPTED_FIELDS", ()):
            if cfg_dict.get(field):
                cfg_dict[field] = self._cipher.encrypt(cfg_dict[field])
        return cfg_dict

    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if not self._validation_service:
            raise RuntimeError("ValidationService not configured")

    def _ensure_card_service(self) -> None:
        """Raise if card service not configured."""
        if not self._card_service:
            raise RuntimeError("CardService not configured")

    def _build_configs_from_rids(
        self, rids: List[str], identity: Identity = None,
    ) -> List[ElementConfigMeta]:
        """Build ElementConfigMeta list from saved resource rids."""
        configs: List[ElementConfigMeta] = []
        for rid in rids:
            resource = self._store.get(rid)
            config = self.resolve(rid, identity=identity)
            configs.append(ElementConfigMeta(
                rid=rid,
                category=resource.category,
                type_key=resource.type,
                name=resource.name,
                config=config,
                dependency_rids=list(resource.nested_refs),
            ))
        return configs

    def _resolve_transitive_deps(self, ref_rids: List[str]) -> List[str]:
        """Resolve refs to ordered list of all transitive dependency rids."""
        return self._dependency_resolver.resolve_all_with_deps(ref_rids)

    def _validate_and_get(
        self,
        ordered_configs: List[ElementConfigMeta],
        target_rid: str,
        timeout_seconds: float,
        user_id: str = "",
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """Validate configs in order and return result for target rid."""
        context = ValidationContext(
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            credential_user_id=credential_user_id,
            auth_service=self._auth_service,
        )
        results = self._validation_service.validate_ordered(ordered_configs, context)
        return results[target_rid]

    def _resolve_builtin_overlay(self, resource: Resource, identity: Identity) -> Dict[str, Any]:
        """Resolve effective config overlay for a built-in resource.

        Uses ReadOnlyHint from the Pydantic schema to identify configurable fields,
        then applies user overrides from builtin_user_configs.
        Priority: user-specific config > team-level config > cfg_dict defaults.
        Decrypts sensitive fields before returning.

        Fields absent from the user config are not included — the caller will
        keep the resource's ``cfg_dict`` value for those.
        """
        if not self._builtin_user_config_repo:
            return {}

        configurable_keys = self._get_configurable_keys(resource.category, resource.type)
        if not configurable_keys:
            return {}

        key = identity_to_key(identity)
        user_config = self._builtin_user_config_repo.get(resource.rid, key)
        if not user_config:
            return {}

        overlay = {k: v for k, v in user_config.fields.items() if k in configurable_keys}

        sensitive_keys = self._get_sensitive_keys(resource.category, resource.type)
        return self._decrypt_config_fields(overlay, sensitive_keys)

    def _get_configurable_keys(self, category: str, type_key: str) -> set:
        """Get field names marked as user-configurable via ReadOnlyHint(read_only=False)."""
        try:
            schema = self.element_registry.get_schema_json(
                ResourceCategory(category), type_key
            )
        except KeyError:
            return set()
        configurable = set()
        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            read_only_hint = hints.get("read_only", {})
            if read_only_hint.get("read_only") is False:
                configurable.add(field_name)
        return configurable

    def _get_sensitive_keys(self, category: str, type_key: str) -> set:
        """Get field names marked as secret from the element's pydantic schema."""
        try:
            schema = self.element_registry.get_schema_json(
                ResourceCategory(category), type_key
            )
        except KeyError:
            return set()
        sensitive = set()
        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            if "secret" in hints:
                sensitive.add(field_name)
        return sensitive

    def _encrypt_config_fields(
        self,
        config: Dict[str, Any],
        sensitive_keys: set,
    ) -> Dict[str, Any]:
        """Encrypt values of fields identified as sensitive by schema hints."""
        if not self._cipher:
            return config
        result = {}
        for k, v in config.items():
            if k in sensitive_keys and v:
                result[k] = self._cipher.encrypt(str(v))
            else:
                result[k] = v
        return result

    def _decrypt_config_fields(
        self,
        config: Dict[str, Any],
        sensitive_keys: set,
    ) -> Dict[str, Any]:
        """Decrypt values of fields identified as sensitive by schema hints."""
        if not self._cipher:
            return config
        result = {}
        for k, v in config.items():
            if k in sensitive_keys and v and isinstance(v, str):
                result[k] = self._cipher.decrypt(v)
            else:
                result[k] = v
        return result
