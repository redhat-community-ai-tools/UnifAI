"""Shared fixtures for resources-service unit tests.

Uses lightweight in-memory fakes for the repository ports instead of Mongo,
and a minimal fake element schema (with real ``SecretHint``/``ReadOnlyHint``
schema hints) instead of the full element catalog, so these tests exercise
the actual encryption/overlay/visibility logic in ``ResourcesService``
without any infrastructure dependencies.
"""
from typing import Any, ClassVar, Dict, List, Optional, Tuple
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field

from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.identity import Identity
from mas.core.field_hints import SecretHint, ReadOnlyHint, CardHint, combine_hints
from mas.resources.models import Resource, ResourceQuery
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import ResourcesService
from mas.resources.builtin_models import BuiltinUserConfig
from mas.validation.service import ElementValidationService
from mas.catalog.card_service import ElementCardService


FAKE_CATEGORY = ResourceCategory.PROVIDER
FAKE_TYPE = "fake_provider"


class FakeProviderConfig(BaseModel):
    """Mimics a real element config: one secret+configurable field via
    schema hints only (no ``ENCRYPTED_FIELDS``, like the real MCP
    ``bearer_token`` field), one configurable field that is sensitive only
    via ``ENCRYPTED_FIELDS`` (no ``SecretHint``, like the real ``api_key``
    field on some LLM/provider configs), one read-only field, and one plain
    field marked with ``CardHint(contexts=["custom"])`` (like the real MCP
    ``mcp_url`` field) to exercise card-visibility schema passthrough."""

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
            CardHint(contexts=["custom"]),
        ),
    )


class FakeElementRegistry:
    """Fake ``ElementRegistry`` exposing a single registered element."""

    def __init__(self):
        self._schemas = {(FAKE_CATEGORY, FAKE_TYPE): FakeProviderConfig}

    def get_schema(self, category, type_key):
        try:
            return self._schemas[(ResourceCategory(category), type_key)]
        except KeyError as exc:
            raise KeyError(f"No schema for {category}:{type_key}") from exc

    def get_schema_json(self, category, type_key):
        return self.get_schema(category, type_key).model_json_schema()


class FakeResourceRepository:
    """In-memory stand-in for ``ResourceRepository``."""

    def __init__(self):
        self._docs: Dict[str, Resource] = {}

    def save(self, doc: Resource) -> str:
        self._docs[doc.rid] = doc
        return doc.rid

    def update(self, doc: Resource) -> str:
        self._docs[doc.rid] = doc
        return doc.rid

    def get(self, rid: str) -> Resource:
        if rid not in self._docs:
            raise KeyError(rid)
        return self._docs[rid]

    def delete(self, rid: str) -> None:
        self._docs.pop(rid, None)

    def find_by_name(self, identity, category, type, name):
        for doc in self._docs.values():
            if (
                doc.identity.type == identity.type
                and doc.identity.id == identity.id
                and doc.category == category
                and doc.type == type
                and doc.name == name
            ):
                return doc
        return None

    def find_resources(self, query: ResourceQuery) -> List[Resource]:
        return list(self._docs.values())

    def count_resources(self, query: ResourceQuery) -> int:
        return len(self._docs)

    def count(self, identity, filter=None) -> int:
        return len(self._docs)

    def meta(self, rid: str):
        doc = self.get(rid)
        return doc.category, doc.type

    def count_nested(self, rid: str) -> int:
        return 0

    def list_nested_usage(self, rid: str) -> List[str]:
        return [doc.rid for doc in self._docs.values() if rid in doc.nested_refs]

    def exists(self, rid: str) -> bool:
        return rid in self._docs

    def count_by_config_field(self, identity, field, value, exclude_rid=""):
        return 0

    def group_count(self, identity, group_by, filter=None):
        return []

    def delete_by_identity(self, identity) -> int:
        return 0

    def find_all_builtins(self, category=None, resource_type=None) -> List[Resource]:
        return [
            d for d in self._docs.values() if d.ownership == ResourceOwnership.BUILTIN
        ]

    def find_builtin_by_url(self, url: str):
        return None

    def set_user_config(self, rid, identity_key, config) -> bool:
        return True


class FakeBlueprintRepository:
    """Only the subset of ``BlueprintRepository`` used by ``ResourcesRegistry``."""

    def list_direct_usage(self, rid: str) -> List[str]:
        return []


class FakeBuiltinUserConfigRepository:
    """In-memory stand-in for ``BuiltinUserConfigRepository``."""

    def __init__(self):
        self._configs: Dict[str, BuiltinUserConfig] = {}

    def _key(self, resource_id, identity_key):
        return f"{resource_id}::{identity_key}"

    def save(self, config: BuiltinUserConfig) -> str:
        self._configs[self._key(config.resource_id, config.identity_key)] = config
        return config.config_id

    def get(self, resource_id: str, identity_key: str) -> Optional[BuiltinUserConfig]:
        return self._configs.get(self._key(resource_id, identity_key))

    def get_by_id(self, config_id: str) -> BuiltinUserConfig:
        for cfg in self._configs.values():
            if cfg.config_id == config_id:
                return cfg
        raise KeyError(config_id)

    def delete(self, resource_id: str, identity_key: str) -> None:
        self._configs.pop(self._key(resource_id, identity_key), None)

    def delete_all_for_resource(self, resource_id: str) -> int:
        keys = [k for k, v in self._configs.items() if v.resource_id == resource_id]
        for k in keys:
            self._configs.pop(k)
        return len(keys)

    def find_by_resource(self, resource_id: str) -> List[BuiltinUserConfig]:
        return [v for v in self._configs.values() if v.resource_id == resource_id]

    def find_by_identity(self, identity_key: str) -> List[BuiltinUserConfig]:
        return [v for v in self._configs.values() if v.identity_key == identity_key]


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
def resource_registry(element_registry) -> ResourcesRegistry:
    from global_utils.utils.crypto import FieldCipher

    return ResourcesRegistry(
        repo=FakeResourceRepository(),
        bp_repo=FakeBlueprintRepository(),
        cipher=FieldCipher(TEST_ENCRYPTION_KEY),
    )


@pytest.fixture
def service(resource_registry, element_registry, builtin_user_config_repo) -> ResourcesService:
    return ResourcesService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        builtin_user_config_repo=builtin_user_config_repo,
        validation_service=Mock(spec=ElementValidationService),
        card_service=Mock(spec=ElementCardService),
        encryption_key=TEST_ENCRYPTION_KEY,
    )


@pytest.fixture
def service_without_config_repo(resource_registry, element_registry) -> ResourcesService:
    """A service with no ``builtin_user_config_repo`` configured."""
    return ResourcesService(
        resource_registry=resource_registry,
        element_registry=element_registry,
        builtin_user_config_repo=None,
        encryption_key=TEST_ENCRYPTION_KEY,
    )
