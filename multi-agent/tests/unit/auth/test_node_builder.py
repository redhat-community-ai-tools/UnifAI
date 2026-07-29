"""Unit tests for NodeBuilder auth_credential injection (static vs registry)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mas.core.auth.credentials.models import StaticAuthMethod
from mas.session.building.category_builders.node_builder import NodeBuilder


def _builder() -> NodeBuilder:
    nb = NodeBuilder.__new__(NodeBuilder)
    nb._get_ref_field_names = lambda cfg: []
    return nb


def _deps(*, bind_return="cred"):
    deps = MagicMock()
    deps.auth_service = MagicMock()
    deps.auth_service.bind_lazy.return_value = bind_return
    deps.execution_ctx = MagicMock()
    deps.execution_ctx.context.credential_user_id.return_value = "user-1"
    return deps


class TestNodeBuilderAuthInjection:
    @pytest.mark.parametrize(
        "server_identifier",
        [
            StaticAuthMethod.NONE.value,
            StaticAuthMethod.ACCESS_TOKEN.value,
            f"{StaticAuthMethod.NONE.value}/",
            f"{StaticAuthMethod.ACCESS_TOKEN.value}/",
        ],
    )
    def test_skips_bind_for_static_auth_methods(self, server_identifier: str):
        deps = _deps()
        cfg = SimpleNamespace(
            server_identifier=server_identifier,
            scheme_type="oauth2",
            model_fields={},
        )

        kwargs = _builder()._extra_kwargs(cfg, MagicMock(), deps)

        assert "auth_credential" not in kwargs
        deps.auth_service.bind_lazy.assert_not_called()

    def test_binds_for_registry_server_identifier(self):
        deps = _deps(bind_return="registry-cred")
        cfg = SimpleNamespace(
            server_identifier="https://auth.example/sso",
            scheme_type="oauth2",
            model_fields={},
        )

        kwargs = _builder()._extra_kwargs(cfg, MagicMock(), deps)

        assert kwargs["auth_credential"] == "registry-cred"
        deps.auth_service.bind_lazy.assert_called_once()
        args = deps.auth_service.bind_lazy.call_args[0]
        assert args[1] == "https://auth.example/sso"
        assert args[2] == "oauth2"

    def test_empty_server_identifier_skips_bind(self):
        deps = _deps()
        cfg = SimpleNamespace(server_identifier="", scheme_type="", model_fields={})

        kwargs = _builder()._extra_kwargs(cfg, MagicMock(), deps)

        assert "auth_credential" not in kwargs
        deps.auth_service.bind_lazy.assert_not_called()
