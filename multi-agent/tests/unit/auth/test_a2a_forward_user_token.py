"""The A2A node can present the acting user's own platform token (ADR-0563 applied to A2A)."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import HttpUrl

from mas.core.identity_forwarding import (
    FORWARD_USER_TOKEN, ForwardedIdentityCredential, IdentityForwarder, IdentityTokenUnavailable,
)
from mas.core.element_deps import ElementBuildContext
from mas.elements.nodes.a2a_agent.a2a_agent_node import A2AAgentNode
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.nodes.a2a_agent.validator import A2AAgentNodeValidator
from mas.elements.common.validator import ValidationContext
from mas.session.building.category_builders.node_builder import NodeBuilder  # noqa: F401


class StaticSource:
    def get_access_token(self, session_id: str, username: str) -> str:
        return "user-jwt"

    def bind(self, *a, **k):
        return None


def _holder():
    holder = MagicMock()
    ctx = MagicMock()
    ctx.session_id = "s1"
    ctx.credential_user_id.return_value = "alice"
    ctx.identity.id = "alice"
    ctx.identity.is_team = False
    ctx.scope = "user"
    ctx.tags = {}
    holder.context = ctx
    return holder


def _cfg(**over: Any) -> A2AAgentNodeConfig:
    data: dict[str, Any] = {
        "base_url": HttpUrl("http://a2a-gateway.zuno-ai-run.svc:8080/agents/tekos"),
        "auth_method": FORWARD_USER_TOKEN,
        "additional_headers": {"X-Zuno-Agent": "tekos", "X-Zuno-Run-Id": "{session_id}"},
    }
    data.update(over)
    return A2AAgentNodeConfig(**data)


def test_config_accepts_the_forward_method_and_headers():
    cfg = _cfg()
    assert cfg.auth_method == "forward_user_token"
    assert cfg.additional_headers["X-Zuno-Agent"] == "tekos"


def test_validator_probes_the_public_card_without_a_user_token():
    headers, err = asyncio.run(
        A2AAgentNodeValidator()._resolve_headers(_cfg(), ValidationContext(credential_user_id="alice"))
    )
    assert headers is None and err is None


def test_builder_binds_the_forwarded_credential_to_the_agent_url():
    builder = NodeBuilder.__new__(NodeBuilder)
    deps = MagicMock(spec=ElementBuildContext)
    deps.identity_token_source = StaticSource()
    deps.execution_ctx = _holder()
    cred = builder._resolve_auth_credential(_cfg(), deps)
    assert isinstance(cred, ForwardedIdentityCredential)
    headers = asyncio.run(cred.get_headers())
    assert headers["Authorization"] == "Bearer user-jwt"
    assert headers["X-Zuno-Agent"] == "tekos" and headers["X-Zuno-Run-Id"] == "s1"


def test_forwarded_token_never_reaches_an_external_agent():
    builder = NodeBuilder.__new__(NodeBuilder)
    deps = MagicMock(spec=ElementBuildContext)
    deps.identity_token_source = StaticSource()
    deps.execution_ctx = _holder()
    cred = builder._resolve_auth_credential(_cfg(base_url=HttpUrl("https://agents.evil.example/a")), deps)
    with pytest.raises(IdentityTokenUnavailable):
        asyncio.run(cred.get_headers())


@contextmanager
def _bridge():
    bridge = MagicMock()
    bridge.run.side_effect = lambda coro: asyncio.run(coro)

    @contextmanager
    def _ctx():
        yield bridge

    with patch("mas.elements.nodes.a2a_agent.a2a_agent_node.get_async_bridge", side_effect=_ctx):
        yield


def test_node_init_defers_when_no_session_can_supply_the_token_yet():
    cred = MagicMock()
    cred.get_headers = AsyncMock(side_effect=IdentityTokenUnavailable("no running session"))
    with _bridge():
        assert A2AAgentNode._resolve_initial_headers(None, cred) is None
