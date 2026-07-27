"""Unit tests for a2a.validate_connection auth-aware validation."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from contextlib import contextmanager

from pydantic import HttpUrl

from mas.actions.providers.a2a.validate_connection.validate_connection import (
    ValidateConnectionAction,
    ValidateConnectionInput,
)
from mas.core.auth.credentials.models import StaticAuthMethod


def _run(coro):
    return asyncio.run(coro)


def _input(**overrides) -> ValidateConnectionInput:
    data = {
        "base_url": HttpUrl("http://a2a.example:8000"),
        "user_id": "user-1",
        "server_identifier": "",
        "auth_method": StaticAuthMethod.NONE.value,
    }
    data.update(overrides)
    return ValidateConnectionInput(**data)


@asynccontextmanager
async def _fake_client(*, agent_card="card", raise_on_enter=None):
    if raise_on_enter is not None:
        raise raise_on_enter
    client = MagicMock()
    client.agent_card = agent_card
    yield client


class TestResolveToken:
    def test_none_returns_no_token(self):
        action = ValidateConnectionAction(auth_service=MagicMock())
        token, msg = _run(action._resolve_token(_input()))
        assert token is None
        assert msg is None

    def test_access_token_uses_bearer(self):
        auth = MagicMock()
        auth.unseal_token.side_effect = lambda t: t
        action = ValidateConnectionAction(auth_service=auth)

        token, msg = _run(
            action._resolve_token(
                _input(
                    auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
                    bearer_token="manual-token",
                )
            )
        )

        assert token == "manual-token"
        assert msg is None

    def test_access_token_missing_returns_auth_required(self):
        action = ValidateConnectionAction(auth_service=MagicMock())
        token, msg = _run(
            action._resolve_token(
                _input(auth_method=StaticAuthMethod.ACCESS_TOKEN.value)
            )
        )
        assert token is None
        assert "Bearer token required" in msg

    def test_sso_uses_get_valid_token(self):
        auth = MagicMock()
        auth.get_valid_token = AsyncMock(return_value="fresh-token")
        action = ValidateConnectionAction(auth_service=auth)

        token, msg = _run(
            action._resolve_token(
                _input(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                )
            )
        )

        assert token == "fresh-token"
        assert msg is None
        auth.get_valid_token.assert_awaited_once_with(
            "user-1", "https://sso.example/realms/x"
        )

    def test_sso_expired_credential_returns_auth_required(self):
        auth = MagicMock()
        auth.get_valid_token = AsyncMock(return_value=None)
        cred = MagicMock()
        cred.is_valid.return_value = False
        auth.get_credential.return_value = cred
        action = ValidateConnectionAction(auth_service=auth)

        token, msg = _run(
            action._resolve_token(
                _input(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                )
            )
        )

        assert token is None
        assert "Session expired" in msg


class TestValidateConnectionExecute:
    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_none_reachable_without_auth(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client()
        action = ValidateConnectionAction()

        out = _run(action.execute(_input()))

        assert out.success is True
        assert out.is_reachable is True
        assert out.authenticated is False
        assert out.status == ""
        mock_client_cls.assert_called_once()
        assert mock_client_cls.call_args.kwargs["headers"] is None

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_access_token_sends_authorization_header(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client()
        auth = MagicMock()
        auth.unseal_token.side_effect = lambda t: t
        action = ValidateConnectionAction(auth_service=auth)

        out = _run(
            action.execute(
                _input(
                    auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
                    bearer_token="manual-token",
                )
            )
        )

        assert out.success is True
        assert out.authenticated is True
        assert mock_client_cls.call_args.kwargs["headers"] == {
            "Authorization": "Bearer manual-token"
        }

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_missing_token_still_reachable_auth_required(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client()
        auth = MagicMock()
        auth.get_valid_token = AsyncMock(return_value=None)
        auth.get_credential.return_value = None
        auth.unseal_token.side_effect = lambda t: t
        action = ValidateConnectionAction(auth_service=auth)

        out = _run(
            action.execute(
                _input(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                )
            )
        )

        assert out.success is True
        assert out.is_reachable is True
        assert out.authenticated is False
        assert out.status == "auth_required"
        assert "Session expired" in out.message

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_401_maps_to_auth_required(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client(
            raise_on_enter=Exception("HTTP 401 Unauthorized")
        )
        auth = MagicMock()
        auth.get_valid_token = AsyncMock(return_value="stale")
        action = ValidateConnectionAction(auth_service=auth)

        out = _run(
            action.execute(
                _input(
                    auth_method="https://sso.example/realms/x",
                    server_identifier="https://sso.example/realms/x",
                )
            )
        )

        assert out.success is True
        assert out.is_reachable is True
        assert out.status == "auth_required"
        assert "rejected credentials" in out.message

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_403_maps_to_auth_required(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client(
            raise_on_enter=Exception("HTTP 403 Forbidden")
        )
        auth = MagicMock()
        auth.unseal_token.side_effect = lambda t: t
        action = ValidateConnectionAction(auth_service=auth)

        out = _run(
            action.execute(
                _input(
                    auth_method=StaticAuthMethod.ACCESS_TOKEN.value,
                    bearer_token="tok",
                )
            )
        )

        assert out.success is True
        assert out.status == "auth_required"
        assert "not authorized" in out.message

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.A2AClient",
    )
    def test_other_errors_fail_unreachable(self, mock_client_cls):
        mock_client_cls.side_effect = lambda **kw: _fake_client(
            raise_on_enter=Exception("connection reset")
        )
        action = ValidateConnectionAction()

        out = _run(action.execute(_input()))

        assert out.success is False
        assert out.is_reachable is False
        assert "connection reset" in out.message

    @patch(
        "mas.actions.providers.a2a.validate_connection.validate_connection.anyio.fail_after",
    )
    def test_timeout_returns_unreachable(self, mock_fail_after):
        @contextmanager
        def _timeout_cm():
            raise TimeoutError()
            yield  # pragma: no cover

        mock_fail_after.return_value = _timeout_cm()
        action = ValidateConnectionAction()

        out = _run(action.execute(_input()))

        assert out.success is False
        assert out.is_reachable is False
        assert "timeout" in out.message.lower()
