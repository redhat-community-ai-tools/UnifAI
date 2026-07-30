"""Unit tests for OAuth endpoint SSRF guardrails."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mas.core.auth.credentials.endpoint_validation import validate_oauth_endpoint
from mas.core.auth.credentials.models import ClientConfig


def _cfg(**kwargs) -> ClientConfig:
    return ClientConfig(client_id="test-client", **kwargs)


class TestValidateOauthEndpoint:
    def test_empty_allowed(self):
        assert validate_oauth_endpoint("", field_name="token_endpoint") == ""
        assert validate_oauth_endpoint("  ", field_name="token_endpoint") == ""

    def test_https_public_host_allowed(self):
        url = "https://auth.redhat.com/auth/realms/EmployeeIDP/protocol/openid-connect/token"
        assert validate_oauth_endpoint(url, field_name="token_endpoint") == url

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost:8080/realms/dev/protocol/openid-connect/token",
            "http://127.0.0.1:8080/token",
            "http://foo.localhost/auth",
            "https://localhost:8443/token",
        ],
    )
    def test_localhost_http_allowed_without_flag(self, url: str, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        assert validate_oauth_endpoint(url, field_name="token_endpoint") == url

    def test_rejects_http_non_local_without_flag(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        with pytest.raises(ValueError, match="must use https"):
            validate_oauth_endpoint(
                "http://auth.example.com/token",
                field_name="token_endpoint",
            )

    def test_rejects_private_ip_without_flag(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        with pytest.raises(ValueError, match="private/reserved"):
            validate_oauth_endpoint(
                "https://10.0.0.5/token",
                field_name="token_endpoint",
            )

    def test_allows_http_and_private_ip_with_flag(self, monkeypatch):
        monkeypatch.setenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", "1")
        http_url = "http://keycloak:8080/realms/dev/protocol/openid-connect/token"
        private_url = "https://10.0.0.5/token"
        assert validate_oauth_endpoint(http_url, field_name="token_endpoint") == http_url
        assert (
            validate_oauth_endpoint(private_url, field_name="token_endpoint")
            == private_url
        )

    def test_rejects_non_http_scheme(self):
        with pytest.raises(ValueError, match="http\\(s\\)"):
            validate_oauth_endpoint("ftp://auth.example.com/token", field_name="token_endpoint")


class TestClientConfigEndpointValidators:
    def test_accepts_rh_sso_defaults(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        cfg = _cfg(
            authorization_endpoint=(
                "https://auth.stage.redhat.com/auth/realms/EmployeeIDP/"
                "protocol/openid-connect/auth"
            ),
            token_endpoint=(
                "https://auth.stage.redhat.com/auth/realms/EmployeeIDP/"
                "protocol/openid-connect/token"
            ),
        )
        assert cfg.token_endpoint.endswith("/token")

    def test_rejects_ssrf_candidate(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        with pytest.raises(ValidationError, match="private/reserved"):
            _cfg(token_endpoint="https://169.254.169.254/latest/meta-data/")

    def test_local_keycloak_http_works(self, monkeypatch):
        monkeypatch.delenv("ALLOW_INSECURE_OAUTH_ENDPOINTS", raising=False)
        cfg = _cfg(
            authorization_endpoint="http://localhost:8080/realms/dev/protocol/openid-connect/auth",
            token_endpoint="http://localhost:8080/realms/dev/protocol/openid-connect/token",
        )
        assert "localhost" in cfg.authorization_endpoint
