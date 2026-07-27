"""Unit tests for ``BuiltinResourceService.find_missing_required_overlay_fields``
scoping a required-secret check to fields that are actually relevant per
``ConditionalHint`` — mirroring the real MCP ``bearer_token`` field, which
is only required when ``auth_method == "access_token"`` (a ``sign_in``-mode
built-in must never be forced through this gate).
"""
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field

from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.field_hints import SecretHint, ReadOnlyHint, ConditionalHint, combine_hints
from mas.core.identity import Identity
from mas.resources.builtin_service import BuiltinResourceService
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.models import Resource


CATEGORY = ResourceCategory.PROVIDER
TYPE_KEY = "fake_auth_provider"


class FakeAuthProviderConfig(BaseModel):
    """Mimics the real ``McpProviderConfig`` auth-method/bearer_token pair:
    a secret+configurable field only relevant when a sibling field has a
    specific value."""

    auth_method: str = Field(default="access_token")
    bearer_token: str | None = Field(
        default=None,
        json_schema_extra=combine_hints(
            SecretHint(),
            ReadOnlyHint(read_only=False),
            ConditionalHint(visible_when={"auth_method": "access_token"}),
        ),
    )


class FakeElementRegistry:
    def get_schema(self, category, type_key):
        return FakeAuthProviderConfig

    def get_schema_json(self, category, type_key):
        return FakeAuthProviderConfig.model_json_schema()


@pytest.fixture
def builtin_service() -> BuiltinResourceService:
    registry = FakeElementRegistry()
    fields = ResourceFieldEncryption(registry, cipher=None)
    return BuiltinResourceService(
        resource_registry=Mock(),
        element_registry=registry,
        field_encryption=fields,
        builtin_user_config_repo=Mock(),
    )


def _builtin_resource() -> Resource:
    return Resource(
        identity=Identity.user("admin"),
        category=CATEGORY,
        type=TYPE_KEY,
        name="fake-builtin",
        cfg_dict={"auth_method": "access_token"},
        ownership=ResourceOwnership.BUILTIN,
        visibility=ResourceVisibility.PUBLIC,
    )


class TestConditionalSecretGate:
    def test_missing_bearer_token_flagged_when_access_token_mode(self, builtin_service):
        resource = _builtin_resource()
        resolved = FakeAuthProviderConfig(auth_method="access_token", bearer_token=None)

        missing = builtin_service.find_missing_required_overlay_fields(resource, resolved)

        assert missing == ["bearer_token"]

    def test_present_bearer_token_not_flagged(self, builtin_service):
        resource = _builtin_resource()
        resolved = FakeAuthProviderConfig(auth_method="access_token", bearer_token="user-own-token")

        missing = builtin_service.find_missing_required_overlay_fields(resource, resolved)

        assert missing == []

    def test_sign_in_mode_never_requires_bearer_token(self, builtin_service):
        """ConditionalHint scoping: bearer_token is irrelevant once the
        resolved config is in sign_in mode, so an empty value must not be
        flagged as a missing overlay."""
        resource = _builtin_resource()
        resolved = FakeAuthProviderConfig(auth_method="sign_in", bearer_token=None)

        missing = builtin_service.find_missing_required_overlay_fields(resource, resolved)

        assert missing == []
