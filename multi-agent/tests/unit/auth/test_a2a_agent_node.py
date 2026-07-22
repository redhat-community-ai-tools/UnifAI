"""Unit tests for A2AAgentNode auth header refresh."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mas.core.auth.errors import AuthError
from mas.elements.nodes.a2a_agent.a2a_agent_node import A2AAgentNode


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
