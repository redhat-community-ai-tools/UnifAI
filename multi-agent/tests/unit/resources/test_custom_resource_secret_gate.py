"""Unit tests for ``ResourceFieldEncryption.find_missing_conditionally_required_secrets``.

Mirrors the real MCP ``bearer_token`` field (``SecretHint`` + ``ConditionalHint``,
only relevant when ``auth_method == "access_token"``) to verify the check works
for *any* resource — custom or built-in — since it operates purely on the
resolved config against its own schema, with no admin/overlay concept.
"""
from typing import Any, Dict

from pydantic import BaseModel, Field

from mas.core.field_hints import SecretHint, ReadOnlyHint, ConditionalHint, combine_hints
from mas.resources.field_encryption import ResourceFieldEncryption


CATEGORY = "providers"
TYPE_KEY = "fake_auth_provider"


class FakeAuthProviderConfig(BaseModel):
    """Fake resolved config mirroring the real MCP ``bearer_token`` field's hints."""

    auth_method: str = Field(default="access_token")
    bearer_token: str | None = Field(
        default=None,
        json_schema_extra=combine_hints(
            SecretHint(),
            ReadOnlyHint(read_only=False),
            ConditionalHint(visible_when={"auth_method": "access_token"}),
        ),
    )
    # A secret field with no ConditionalHint — must never be flagged, since
    # "optional and unset" is a legitimate state with no schema signal saying
    # otherwise (e.g. an optional API key some servers don't require).
    optional_api_key: str | None = Field(
        default=None,
        json_schema_extra=combine_hints(SecretHint(), ReadOnlyHint(read_only=False)),
    )


class FakeElementRegistry:
    """Fake ``ElementRegistry`` exposing a single registered element's schema."""

    def get_schema_json(self, category: str, type_key: str) -> Dict[str, Any]:
        if (category, type_key) != (CATEGORY, TYPE_KEY):
            raise KeyError((category, type_key))
        return FakeAuthProviderConfig.model_json_schema()


def _fields() -> ResourceFieldEncryption:
    return ResourceFieldEncryption(FakeElementRegistry(), cipher=None)


class TestFindMissingConditionallyRequiredSecrets:
    """Tests for ``ResourceFieldEncryption.find_missing_conditionally_required_secrets``."""

    def test_flags_empty_bearer_token_when_access_token_mode(self) -> None:
        resolved = FakeAuthProviderConfig(auth_method="access_token", bearer_token=None)

        missing = _fields().find_missing_conditionally_required_secrets(
            CATEGORY, TYPE_KEY, resolved
        )

        assert missing == ["bearer_token"]

    def test_does_not_flag_when_bearer_token_present(self) -> None:
        resolved = FakeAuthProviderConfig(auth_method="access_token", bearer_token="tok-123")

        missing = _fields().find_missing_conditionally_required_secrets(
            CATEGORY, TYPE_KEY, resolved
        )

        assert missing == []

    def test_sign_in_mode_never_requires_bearer_token(self) -> None:
        resolved = FakeAuthProviderConfig(auth_method="sign_in", bearer_token=None)

        missing = _fields().find_missing_conditionally_required_secrets(
            CATEGORY, TYPE_KEY, resolved
        )

        assert missing == []

    def test_secret_without_conditional_hint_is_never_flagged(self) -> None:
        """A secret field with no ConditionalHint is left alone even when
        empty — this check is intentionally scoped to fields the schema
        explicitly ties to another field's value."""
        resolved = FakeAuthProviderConfig(
            auth_method="access_token", bearer_token="tok-123", optional_api_key=None,
        )

        missing = _fields().find_missing_conditionally_required_secrets(
            CATEGORY, TYPE_KEY, resolved
        )

        assert missing == []

    def test_unknown_type_returns_empty(self) -> None:
        resolved = FakeAuthProviderConfig()

        missing = _fields().find_missing_conditionally_required_secrets(
            CATEGORY, "does-not-exist", resolved
        )

        assert missing == []
