"""Unit tests for A2AAgentNode auth header refresh and init headers."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mas.core.auth.errors import AuthError
from mas.elements.nodes.a2a_agent.a2a_agent_node import A2AAgentNode
# Stubbed in init tests so constructing A2AAgentNode skips real BaseNode wiring.
from mas.elements.nodes.common.base_node import BaseNode


def _node(*, auth_credential=None) -> MagicMock:
    node = MagicMock(spec=A2AAgentNode)
    node.uid = "a2a-node-1"
    node._auth_credential = auth_credential
    node.a2a_provider = MagicMock()
    return node


@contextmanager
def _bridge_runs_coroutines():
    bridge = MagicMock()
    bridge.run.side_effect = lambda coro: asyncio.run(coro)

    @contextmanager
    def _ctx():
        yield bridge

    with patch(
        "mas.elements.nodes.a2a_agent.a2a_agent_node.get_async_bridge",
        side_effect=_ctx,
    ):
        yield


class TestResolveInitialHeaders:
    def test_prefers_auth_credential_headers(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(return_value={"Authorization": "Bearer oauth"})

        with _bridge_runs_coroutines():
            headers = A2AAgentNode._resolve_initial_headers("raw-token", cred)

        assert headers == {"Authorization": "Bearer oauth"}

    def test_falls_back_to_bearer_when_credential_unavailable(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(side_effect=AuthError("no user yet"))

        with _bridge_runs_coroutines():
            headers = A2AAgentNode._resolve_initial_headers("raw-token", cred)

        assert headers == {"Authorization": "Bearer raw-token"}

    def test_returns_none_when_neither_available(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(side_effect=AuthError("no user yet"))

        with _bridge_runs_coroutines():
            headers = A2AAgentNode._resolve_initial_headers(None, cred)

        assert headers is None


class TestA2AAgentNodeInitProvider:
    @patch("mas.elements.nodes.a2a_agent.a2a_agent_node.A2AProvider")
    def test_create_sync_uses_credential_headers(self, mock_provider):
        cred = MagicMock()
        cred.get_headers = AsyncMock(return_value={"Authorization": "Bearer oauth"})
        mock_provider.create_sync.return_value = MagicMock()

        with _bridge_runs_coroutines():
            with patch.object(BaseNode, "__init__", return_value=None):
                A2AAgentNode(
                    base_url="http://agent.example",
                    auth_credential=cred,
                )

        mock_provider.create_sync.assert_called_once()
        assert mock_provider.create_sync.call_args.kwargs["headers"] == {
            "Authorization": "Bearer oauth"
        }

    @patch("mas.elements.nodes.a2a_agent.a2a_agent_node.A2AProvider")
    def test_defers_create_sync_when_sso_headers_unavailable(self, mock_provider):
        cred = MagicMock()
        cred.get_headers = AsyncMock(side_effect=AuthError("no user yet"))
        mock_provider.return_value = MagicMock()

        with _bridge_runs_coroutines():
            with patch.object(BaseNode, "__init__", return_value=None):
                A2AAgentNode(
                    base_url="http://agent.example",
                    auth_credential=cred,
                )

        mock_provider.create_sync.assert_not_called()
        mock_provider.assert_called_once()
        assert mock_provider.call_args.kwargs.get("headers") is None


class TestA2AAgentNodeRefreshAuthHeaders:
    def test_noop_without_auth_credential(self):
        node = _node(auth_credential=None)
        A2AAgentNode._refresh_auth_headers(node)
        node.a2a_provider.update_headers.assert_not_called()

    def test_updates_provider_headers_from_credential(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(return_value={"Authorization": "Bearer refreshed"})
        node = _node(auth_credential=cred)

        with _bridge_runs_coroutines():
            A2AAgentNode._refresh_auth_headers(node)

        node.a2a_provider.update_headers.assert_called_once_with(
            {"Authorization": "Bearer refreshed"}
        )

    def test_empty_headers_fail_closed(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(return_value={})
        node = _node(auth_credential=cred)

        with _bridge_runs_coroutines():
            with pytest.raises(RuntimeError, match="no headers"):
                A2AAgentNode._refresh_auth_headers(node)

        node.a2a_provider.update_headers.assert_not_called()

    def test_auth_error_propagates(self):
        cred = MagicMock()
        cred.get_headers = AsyncMock(side_effect=AuthError("expired"))
        node = _node(auth_credential=cred)

        with _bridge_runs_coroutines():
            with pytest.raises(AuthError):
                A2AAgentNode._refresh_auth_headers(node)
