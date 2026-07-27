"""Unit tests for A2AProviderFactory auth_credential wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import HttpUrl

from mas.core.auth.credentials.models import StaticAuthMethod
from mas.elements.providers.a2a_client.a2a_provider_factory import A2AProviderFactory
from mas.elements.providers.a2a_client.config import A2AProviderConfig


def _cfg(**overrides) -> A2AProviderConfig:
    data = {
        "base_url": HttpUrl("http://a2a.example:8000"),
        "auth_method": StaticAuthMethod.NONE.value,
    }
    data.update(overrides)
    return A2AProviderConfig(**data)


class TestA2AProviderFactoryAuth:
    """Ensure ProviderBuilder-injected auth_credential is not dropped."""

    @patch(
        "mas.elements.providers.a2a_client.a2a_provider_factory.A2AProvider.create_sync"
    )
    def test_passes_auth_credential_to_provider(self, mock_create_sync):
        factory = A2AProviderFactory()
        cred = MagicMock(name="auth_credential")
        cfg = _cfg(
            auth_method="https://sso.example/realms/x",
            server_identifier="https://sso.example/realms/x",
        )

        factory.create(cfg, auth_credential=cred)

        mock_create_sync.assert_called_once()
        assert mock_create_sync.call_args.kwargs["auth"] is cred

    @patch(
        "mas.elements.providers.a2a_client.a2a_provider_factory.A2AProvider.create_sync"
    )
    def test_access_token_sets_authorization_header(self, mock_create_sync):
        factory = A2AProviderFactory()
        cfg = _cfg(
            auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
            bearer_token="manual-token",
        )

        factory.create(cfg)

        headers = mock_create_sync.call_args.kwargs["headers"]
        assert headers == {"Authorization": "Bearer manual-token"}
        assert mock_create_sync.call_args.kwargs["auth"] is None

    @patch(
        "mas.elements.providers.a2a_client.a2a_provider_factory.A2AProvider.create",
        new_callable=AsyncMock,
    )
    def test_create_async_passes_auth_credential(self, mock_create):
        factory = A2AProviderFactory()
        cred = MagicMock(name="auth_credential")
        cfg = _cfg(
            auth_method="https://sso.example/realms/x",
            server_identifier="https://sso.example/realms/x",
        )

        import asyncio

        asyncio.run(factory.create_async(cfg, auth_credential=cred))

        mock_create.assert_awaited_once()
        assert mock_create.call_args.kwargs["auth"] is cred
