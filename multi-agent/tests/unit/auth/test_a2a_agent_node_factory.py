"""Unit tests for A2AAgentNodeFactory auth path selection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import HttpUrl

from mas.core.auth.credentials.models import StaticAuthMethod
from mas.elements.nodes.a2a_agent.a2a_agent_node_factory import A2AAgentNodeFactory
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig


def _cfg(**overrides) -> A2AAgentNodeConfig:
    data = {
        "base_url": HttpUrl("http://a2a.example:8000"),
        "auth_method": StaticAuthMethod.NONE.value,
        "bearer_token": None,
    }
    data.update(overrides)
    return A2AAgentNodeConfig(**data)


class TestA2AAgentNodeFactoryAuth:
    @patch("mas.elements.nodes.a2a_agent.a2a_agent_node_factory.A2AAgentNode")
    def test_access_token_passes_bearer_when_no_credential(self, mock_node):
        factory = A2AAgentNodeFactory()
        cfg = _cfg(
            auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
            bearer_token="manual-token",
        )

        factory.create(cfg, retriever=None)

        kwargs = mock_node.call_args.kwargs
        assert kwargs["bearer_token"] == "manual-token"
        assert kwargs["auth_credential"] is None

    @patch("mas.elements.nodes.a2a_agent.a2a_agent_node_factory.A2AAgentNode")
    def test_auth_credential_skips_bearer_token(self, mock_node):
        factory = A2AAgentNodeFactory()
        cfg = _cfg(
            auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
            bearer_token="manual-token",
        )
        cred = MagicMock(name="auth_credential")

        factory.create(cfg, retriever=None, auth_credential=cred)

        kwargs = mock_node.call_args.kwargs
        assert kwargs["auth_credential"] is cred
        assert kwargs["bearer_token"] is None

    @patch("mas.elements.nodes.a2a_agent.a2a_agent_node_factory.A2AAgentNode")
    def test_none_auth_has_no_bearer_or_credential(self, mock_node):
        factory = A2AAgentNodeFactory()
        cfg = _cfg(auth_method=StaticAuthMethod.NONE.value)

        factory.create(cfg, retriever=None)

        kwargs = mock_node.call_args.kwargs
        assert kwargs["bearer_token"] is None
        assert kwargs["auth_credential"] is None
