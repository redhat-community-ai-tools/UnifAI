"""Unit tests for A2A agent node card-grid validator (auth-aware)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic import HttpUrl

from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.auth.errors import TokenExpiredError
from mas.elements.common.validator import ValidationCode, ValidationContext
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.nodes.a2a_agent.validator import A2AAgentNodeValidator


def _run(coro):
    return asyncio.run(coro)


def _config(**overrides) -> A2AAgentNodeConfig:
    data = {
        "base_url": HttpUrl("http://a2a.example:8000"),
        "auth_method": StaticAuthMethod.NONE.value,
    }
    data.update(overrides)
    return A2AAgentNodeConfig(**data)


def _context(**overrides) -> ValidationContext:
    data = {
        "timeout_seconds": 5.0,
        "user_id": "owner-1",
        "credential_user_id": "user-1",
        "auth_service": None,
    }
    data.update(overrides)
    return ValidationContext(**data)


@asynccontextmanager
async def _fake_client(*, agent_card="card", raise_on_enter=None):
    if raise_on_enter is not None:
        raise raise_on_enter
    client = MagicMock()
    client.agent_card = agent_card
    yield client


@contextmanager
def _bridge_that_runs():
    bridge = MagicMock()
    bridge.run.side_effect = lambda coro, *a, **k: _run(coro)
    bridge.__enter__ = MagicMock(return_value=bridge)
    bridge.__exit__ = MagicMock(return_value=False)
    with patch(
        "mas.elements.nodes.a2a_agent.validator.get_async_bridge",
        return_value=bridge,
    ):
        yield bridge


class TestResolveHeaders:
    def test_none_returns_no_headers(self):
        validator = A2AAgentNodeValidator()
        headers, err = _run(
            validator._resolve_headers(_config(), _context())
        )
        assert headers is None
        assert err is None

    def test_access_token_uses_bearer(self):
        auth = MagicMock()
        auth.unseal_token.side_effect = lambda t: t
        validator = A2AAgentNodeValidator()

        headers, err = _run(
            validator._resolve_headers(
                _config(
                    auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
                    bearer_token="manual-token",
                ),
                _context(auth_service=auth),
            )
        )

        assert headers == {"Authorization": "Bearer manual-token"}
        assert err is None

    def test_access_token_missing_returns_error(self):
        validator = A2AAgentNodeValidator()
        headers, err = _run(
            validator._resolve_headers(
                _config(auth_method=StaticAuthMethod.ACCESS_TOKEN.value),
                _context(auth_service=MagicMock()),
            )
        )
        assert headers is None
        assert "Bearer token required" in err

    def test_sso_uses_bind_and_headers(self):
        auth_cred = MagicMock()
        auth_cred.get_headers = AsyncMock(
            return_value={"Authorization": "Bearer fresh"}
        )
        auth = MagicMock()
        auth.bind.return_value = auth_cred
        validator = A2AAgentNodeValidator()

        headers, err = _run(
            validator._resolve_headers(
                _config(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                ),
                _context(auth_service=auth),
            )
        )

        assert headers == {"Authorization": "Bearer fresh"}
        assert err is None
        auth.bind.assert_called_once_with(
            "user-1",
            "https://sso.example/realms/x",
            scheme_type="",
        )

    def test_sso_missing_credential_returns_error(self):
        auth = MagicMock()
        auth.bind.return_value = None
        validator = A2AAgentNodeValidator()

        headers, err = _run(
            validator._resolve_headers(
                _config(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                ),
                _context(auth_service=auth),
            )
        )

        assert headers is None
        assert "Session expired" in err

    def test_sso_expired_token_returns_error(self):
        auth_cred = MagicMock()
        auth_cred.get_headers = AsyncMock(
            side_effect=TokenExpiredError("expired")
        )
        auth = MagicMock()
        auth.bind.return_value = auth_cred
        validator = A2AAgentNodeValidator()

        headers, err = _run(
            validator._resolve_headers(
                _config(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                ),
                _context(auth_service=auth),
            )
        )

        assert headers is None
        assert "Session expired" in err


class TestValidate:
    def test_none_auth_connection_ok(self):
        validator = A2AAgentNodeValidator()
        with _bridge_that_runs(), patch(
            "mas.elements.nodes.a2a_agent.validator.A2AClient",
            side_effect=lambda **kw: _fake_client(),
        ):
            report = validator.validate(_config(), _context())

        assert report.is_valid
        assert any(m.code == "CONNECTION_OK" for m in report.messages)

    def test_sso_missing_marks_invalid_credentials(self):
        auth = MagicMock()
        auth.bind.return_value = None
        validator = A2AAgentNodeValidator()

        with _bridge_that_runs():
            report = validator.validate(
                _config(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                ),
                _context(auth_service=auth),
            )

        assert not report.is_valid
        assert any(
            m.code == ValidationCode.INVALID_CREDENTIALS.value
            for m in report.messages
        )

    def test_401_marks_invalid_credentials(self):
        validator = A2AAgentNodeValidator()
        with _bridge_that_runs(), patch(
            "mas.elements.nodes.a2a_agent.validator.A2AClient",
            side_effect=lambda **kw: _fake_client(
                raise_on_enter=RuntimeError("401 Unauthorized")
            ),
        ):
            report = validator.validate(_config(), _context())

        assert not report.is_valid
        assert any(
            m.code == ValidationCode.INVALID_CREDENTIALS.value
            for m in report.messages
        )

    def test_access_token_missing_marks_invalid(self):
        validator = A2AAgentNodeValidator()
        with _bridge_that_runs():
            report = validator.validate(
                _config(auth_method=StaticAuthMethod.ACCESS_TOKEN.value),
                _context(auth_service=MagicMock()),
            )

        assert not report.is_valid
        assert any(
            m.code == ValidationCode.INVALID_CREDENTIALS.value
            for m in report.messages
        )
