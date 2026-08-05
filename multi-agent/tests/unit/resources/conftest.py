"""Shared fixtures for resources-service unit tests.

Uses lightweight in-memory fakes for the repository ports instead of Mongo,
and a minimal fake element schema (with real ``SecretHint``/``ReadOnlyHint``
schema hints) instead of the full element catalog, so these tests exercise
the actual encryption/overlay/visibility logic in ``ResourcesService`` /
``BuiltinResourceService`` without any infrastructure dependencies.
"""
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field

from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.identity import Identity
from mas.core.field_hints import SecretHint, ReadOnlyHint, CardHint, CardContext, combine_hints
from mas.resources.models import Resource, ResourceQuery
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import ResourcesService
from mas.resources.builtin_service import BuiltinResourceService
from mas.resources.builtin_models import BuiltinResourceDescriptor, BuiltinUserConfig
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.repository.builtin_resource_descriptor_repository import (
    BuiltinResourceDescriptorRepository,
)
from mas.validation.service import ElementValidationService
from mas.catalog.card_service import ElementCardService

from global_utils.utils.crypto import FieldCipher

FAKE_CATEGORY = ResourceCategory.PROVIDER
FAKE_TYPE = "fake_provider"


class FakeProviderConfig(BaseModel):
    """Mimics a real element config: one secret+configurable field via
    schema hints only (no ``ENCRYPTED_FIELDS``, like the real MCP
    ``bearer_token`` field), one configurable field that is sensitive only
    via ``ENCRYPTED_FIELDS`` (no ``SecretHint``, like the real ``api_key``
    field on some LLM/provider configs), one read-only field, and one plain
    field marked with ``CardHint(contexts=[CardContext.CUSTOM])`` (like the
    real MCP ``mcp_url`` field) to exercise card-visibility schema
    passthrough."""

    ENCRYPTED_FIELDS: ClassVar[Tuple[str, ...]] = ("api_key",)

    bearer_token: Optional[str] = Field(
        default=None,
        json_schema_extra=combine_hints(
            SecretHint(),
            ReadOnlyHint(read_only=False),
        ),
    )
    api_key: Optional[str] = Field(
        default=None,
        json_schema_extra=combine_hints(
            ReadOnlyHint(read_only=False),
        ),
    )
    endpoint: str = Field(
        default="https://example.com",
        json_schema_extra=combine_hints(
            CardHint(contexts=[CardContext.CUSTOM]),
        ),
    )


class FakeElementRegistry:
    """Fake ``ElementRegistry`` exposing a single registered element."""

    def __init__(self) -> None:
        self._schemas = {(FAKE_CATEGORY, FAKE_TYPE): FakeProviderConfig}

    def get_schema(self, category: str, type_key: str) -> type:
        try:
            return self._schemas[(ResourceCategory(category), type_key)]
        except KeyError as exc:
            raise KeyError(f"No schema for {category}:{type_key}") from exc

    def get_schema_json(self, category: str, type_key: str) -> Dict[str, Any]:
        return self.get_schema(category, type_key).model_json_schema()


class FakeResourceRepository:
    """In-memory stand-in for ``ResourceRepository``.

    Stores/returns deep copies (like a real Mongo round-trip would) rather
    than the caller's live object — otherwise mutating a ``Resource`` the
    caller already holds (e.g. before calling ``update()``) would silently
    also mutate the "persisted" copy, masking bugs in code that compares
    a doc's new state against what's actually stored.

    Carries no ownership/visibility knowledge — that lives entirely in
    ``FakeBuiltinResourceDescriptorRepository`` below, which is handed this
    same instance so its joined queries see the same underlying docs a real
    Mongo ``$lookup`` would.
    """

    def __init__(self) -> None:
        self._docs: Dict[str, Resource] = {}

    def save(self, doc: Resource) -> str:
        self._docs[doc.rid] = doc.model_copy(deep=True)
        return doc.rid

    def update(self, doc: Resource) -> str:
        self._docs[doc.rid] = doc.model_copy(deep=True)
        return doc.rid

    def get(self, rid: str) -> Resource:
        if rid not in self._docs:
            raise KeyError(rid)
        return self._docs[rid].model_copy(deep=True)

    def delete(self, rid: str) -> None:
        self._docs.pop(rid, None)

    def find_by_name(
        self, identity: Identity, category: str, type: str, name: str,
    ) -> Optional[Resource]:
        for doc in self._docs.values():
            if (
                doc.identity.type == identity.type
                and doc.identity.id == identity.id
                and doc.category == category
                and doc.type == type
                and doc.name == name
            ):
                return doc.model_copy(deep=True)
        return None

    def _matches_query(self, doc: Resource, query: ResourceQuery) -> bool:
        """Mirror ``MongoResourceRepository._build_resource_filter`` semantics
        (plain identity+category+type — no ownership/visibility, which are
        no longer part of ``ResourceQuery``)."""
        identity_match = (
            doc.identity.type == query.identity.type
            and doc.identity.id == query.identity.id
        )
        if query.category and doc.category != query.category:
            return False
        if query.type and doc.type != query.type:
            return False
        return identity_match

    def find_resources(self, query: ResourceQuery) -> List[Resource]:
        return [
            doc.model_copy(deep=True)
            for doc in self._docs.values()
            if self._matches_query(doc, query)
        ]

    def count_resources(self, query: ResourceQuery) -> int:
        return sum(1 for doc in self._docs.values() if self._matches_query(doc, query))

    def count(self, identity: Identity, filter: Optional[dict] = None) -> int:
        return len(self._docs)

    def meta(self, rid: str) -> Tuple[str, str]:
        doc = self.get(rid)
        return doc.category, doc.type

    def count_nested(self, rid: str) -> int:
        return 0

    def list_nested_usage(self, rid: str) -> List[str]:
        return [doc.rid for doc in self._docs.values() if rid in doc.nested_refs]

    def exists(self, rid: str) -> bool:
        return rid in self._docs

    def count_by_config_field(
        self, identity: Identity, field: str, value: Any, exclude_rid: str = "",
    ) -> int:
        return 0

    def group_count(
        self, identity: Identity, group_by: List[str], filter: Optional[dict] = None,
    ) -> list:
        return []

    def delete_by_identity(self, identity: Identity) -> int:
        return 0


class FakeBuiltinResourceDescriptorRepository(BuiltinResourceDescriptorRepository):
    """In-memory stand-in for ``BuiltinResourceDescriptorRepository``.

    Shares the same ``FakeResourceRepository`` instance as the
    ``ResourcesRegistry`` under test, so its joined queries
    (``find_all_builtins``/``find_visible_for_identity``) see the same
    underlying ``Resource`` docs a real Mongo ``$lookup`` against the
    ``resources`` collection would.
    """

    def __init__(self, resource_repo: FakeResourceRepository) -> None:
        self._resource_repo = resource_repo
        self._descriptors: Dict[str, BuiltinResourceDescriptor] = {}

    def get(self, rid: str) -> Optional[BuiltinResourceDescriptor]:
        descriptor = self._descriptors.get(rid)
        return descriptor.model_copy(deep=True) if descriptor else None

    def save(self, descriptor: BuiltinResourceDescriptor) -> str:
        self._descriptors[descriptor.rid] = descriptor.model_copy(deep=True)
        return descriptor.rid

    def delete(self, rid: str) -> None:
        self._descriptors.pop(rid, None)

    def find_all_rids(self) -> List[str]:
        return list(self._descriptors.keys())

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        result = []
        for rid in self._descriptors:
            try:
                doc = self._resource_repo.get(rid)
            except KeyError:
                continue
            if category and doc.category != category:
                continue
            if resource_type and doc.type != resource_type:
                continue
            result.append(doc)
        return result

    def find_visible_for_identity(
        self,
        *,
        identity: Optional[Identity],
        category: Optional[str],
        resource_type: Optional[str],
        ownership: Optional[ResourceOwnership],
        is_admin: bool,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> Tuple[List[Resource], int]:
        matches: List[Resource] = []
        for doc in self._resource_repo._docs.values():
            descriptor = self._descriptors.get(doc.rid)
            is_builtin_doc = descriptor is not None

            if ownership == ResourceOwnership.BUILTIN:
                if not is_builtin_doc:
                    continue
                if not is_admin and descriptor.visibility != ResourceVisibility.PUBLIC:
                    continue
            elif ownership == ResourceOwnership.CUSTOM:
                if is_builtin_doc:
                    continue
                if identity is None or doc.identity.type != identity.type or doc.identity.id != identity.id:
                    continue
            else:
                identity_match = (
                    identity is not None
                    and doc.identity.type == identity.type
                    and doc.identity.id == identity.id
                )
                builtin_public = is_builtin_doc and descriptor.visibility == ResourceVisibility.PUBLIC
                if not (identity_match or builtin_public):
                    continue

            if category and doc.category != category:
                continue
            if resource_type and doc.type != resource_type:
                continue
            matches.append(doc.model_copy(deep=True))

        total = len(matches)
        matches.sort(key=lambda d: getattr(d, sort_by), reverse=(sort_order == "desc"))
        return matches[offset:offset + limit], total


class FakeBlueprintRepository:
    """Only the subset of ``BlueprintRepository`` used by ``ResourcesRegistry``."""

    def list_direct_usage(self, rid: str) -> List[str]:
        return []


class FakeBuiltinUserConfigRepository:
    """In-memory stand-in for ``BuiltinUserConfigRepository``."""

    def __init__(self) -> None:
        self._configs: Dict[str, BuiltinUserConfig] = {}

    def _key(self, resource_id: str, identity_key: str) -> str:
        return f"{resource_id}::{identity_key}"

    def save(self, config: BuiltinUserConfig) -> str:
        self._configs[self._key(config.resource_id, config.identity_key)] = config.model_copy(deep=True)
        return config.config_id

    def get(self, resource_id: str, identity_key: str) -> Optional[BuiltinUserConfig]:
        cfg = self._configs.get(self._key(resource_id, identity_key))
        return cfg.model_copy(deep=True) if cfg else None

    def get_by_id(self, config_id: str) -> BuiltinUserConfig:
        for cfg in self._configs.values():
            if cfg.config_id == config_id:
                return cfg.model_copy(deep=True)
        raise KeyError(config_id)

    def delete(self, resource_id: str, identity_key: str) -> None:
        self._configs.pop(self._key(resource_id, identity_key), None)

    def delete_all_for_resource(self, resource_id: str) -> int:
        keys = [k for k, v in self._configs.items() if v.resource_id == resource_id]
        for k in keys:
            self._configs.pop(k)
        return len(keys)

    def find_by_identity(self, identity_key: str) -> List[BuiltinUserConfig]:
        return [v.model_copy(deep=True) for v in self._configs.values() if v.identity_key == identity_key]


TEST_ENCRYPTION_KEY = "g67-nhpC145BVaYc0Wy4-OYTVIDv_huAmAZbvu92IQA="


@pytest.fixture
def alice() -> Identity:
    return Identity.user("alice")


@pytest.fixture
def bob() -> Identity:
    return Identity.user("bob")


@pytest.fixture
def admin_identity() -> Identity:
    return Identity.user("admin")


@pytest.fixture
def element_registry() -> FakeElementRegistry:
    return FakeElementRegistry()


@pytest.fixture
def builtin_user_config_repo() -> FakeBuiltinUserConfigRepository:
    return FakeBuiltinUserConfigRepository()


@pytest.fixture
def resource_repo() -> FakeResourceRepository:
    return FakeResourceRepository()


@pytest.fixture
def resource_registry(resource_repo, element_registry) -> ResourcesRegistry:
    return ResourcesRegistry(
        repo=resource_repo,
        bp_repo=FakeBlueprintRepository(),
        cipher=FieldCipher(TEST_ENCRYPTION_KEY),
    )


@pytest.fixture
def builtin_resource_descriptor_repo(resource_repo) -> FakeBuiltinResourceDescriptorRepository:
    return FakeBuiltinResourceDescriptorRepository(resource_repo)


@pytest.fixture
def builtin_service(
    resource_registry, element_registry, builtin_resource_descriptor_repo, builtin_user_config_repo,
) -> BuiltinResourceService:
    field_encryption = ResourceFieldEncryption(element_registry, FieldCipher(TEST_ENCRYPTION_KEY))
    return BuiltinResourceService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        field_encryption=field_encryption,
        descriptor_repo=builtin_resource_descriptor_repo,
        builtin_user_config_repo=builtin_user_config_repo,
    )


@pytest.fixture
def builtin_service_without_config_repo(
    resource_registry, element_registry, builtin_resource_descriptor_repo,
) -> BuiltinResourceService:
    """A ``BuiltinResourceService`` with no ``builtin_user_config_repo``
    configured — pairs with ``service_without_config_repo`` below."""
    field_encryption = ResourceFieldEncryption(element_registry, FieldCipher(TEST_ENCRYPTION_KEY))
    return BuiltinResourceService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        field_encryption=field_encryption,
        descriptor_repo=builtin_resource_descriptor_repo,
        builtin_user_config_repo=None,
    )


@pytest.fixture
def service(resource_registry, element_registry, builtin_user_config_repo, builtin_service) -> ResourcesService:
    field_encryption = ResourceFieldEncryption(element_registry, FieldCipher(TEST_ENCRYPTION_KEY))
    return ResourcesService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        builtin_service=builtin_service,
        field_encryption=field_encryption,
        builtin_user_config_repo=builtin_user_config_repo,
        validation_service=Mock(spec=ElementValidationService),
        card_service=Mock(spec=ElementCardService),
    )


@pytest.fixture
def service_without_config_repo(
    resource_registry, element_registry, builtin_service_without_config_repo,
) -> ResourcesService:
    """A service with no ``builtin_user_config_repo`` configured."""
    field_encryption = ResourceFieldEncryption(element_registry, FieldCipher(TEST_ENCRYPTION_KEY))
    return ResourcesService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        builtin_service=builtin_service_without_config_repo,
        field_encryption=field_encryption,
        builtin_user_config_repo=None,
    )
