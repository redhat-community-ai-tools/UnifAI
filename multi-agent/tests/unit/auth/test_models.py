"""Unit tests for ClientConfig reserved server_identifier validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mas.core.auth.credentials.models import ClientConfig, StaticAuthMethod


def _cfg(**kwargs) -> ClientConfig:
    return ClientConfig(client_id="test-client", **kwargs)


class TestClientConfigReservedIds:
    @pytest.mark.parametrize(
        "server_identifier",
        [
            StaticAuthMethod.NONE.value,
            StaticAuthMethod.ACCESS_TOKEN.value,
            f"{StaticAuthMethod.NONE.value}/",
            f"{StaticAuthMethod.ACCESS_TOKEN.value}/",
            "none///",
            "access_token/",
        ],
    )
    def test_rejects_reserved_identifiers(self, server_identifier: str):
        with pytest.raises(ValidationError, match="reserved"):
            _cfg(server_identifier=server_identifier)

    def test_normalizes_trailing_slash_on_accepted_id(self):
        cfg = _cfg(server_identifier="https://auth.example/sso/")
        assert cfg.server_identifier == "https://auth.example/sso"

    def test_accepts_non_reserved_identifier(self):
        cfg = _cfg(server_identifier="rh-sso-prod")
        assert cfg.server_identifier == "rh-sso-prod"

    def test_empty_identifier_allowed(self):
        cfg = _cfg(server_identifier="")
        assert cfg.server_identifier == ""
