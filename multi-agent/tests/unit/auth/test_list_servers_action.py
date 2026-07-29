"""Unit tests for auth.list_servers (static options + registry merge)."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from mas.actions.auth.list_servers.action import (
    ListServersAction,
    ListServersInput,
)
from mas.core.auth.credentials.models import ClientConfig, StaticAuthMethod


def _run(coro):
    return asyncio.run(coro)


class TestListServersAction:
    def test_empty_category_fails(self):
        action = ListServersAction(server_config_store=MagicMock())
        result = _run(action.execute(ListServersInput(category="")))

        assert result.success is False
        assert result.servers == []
        assert "required" in result.message.lower()

    def test_valid_category_includes_static_options_without_store(self):
        action = ListServersAction(server_config_store=None)
        result = _run(action.execute(ListServersInput(category="a2a")))

        assert result.success is True
        assert result.servers == [
            {"label": "None", "value": StaticAuthMethod.NONE.value},
            {"label": "Access Token", "value": StaticAuthMethod.ACCESS_TOKEN.value},
        ]

    def test_merges_registry_entries_with_display_name_fallback(self):
        store = MagicMock()
        store.list_by_category.return_value = [
            ClientConfig(
                client_id="c1",
                server_identifier="https://auth.example/sso",
                display_name="RH SSO",
                categories=["a2a"],
            ),
            ClientConfig(
                client_id="c2",
                server_identifier="https://auth.example/other",
                display_name="",
                categories=["a2a"],
            ),
        ]
        action = ListServersAction(server_config_store=store)
        result = _run(action.execute(ListServersInput(category="a2a")))

        store.list_by_category.assert_called_once_with("a2a")
        assert result.success is True
        assert result.servers[:2] == [
            {"label": "None", "value": StaticAuthMethod.NONE.value},
            {"label": "Access Token", "value": StaticAuthMethod.ACCESS_TOKEN.value},
        ]
        assert result.servers[2:] == [
            {"label": "RH SSO", "value": "https://auth.example/sso"},
            {
                "label": "https://auth.example/other",
                "value": "https://auth.example/other",
            },
        ]

    @pytest.mark.parametrize("category", ["a2a", "mcp"])
    def test_passes_category_to_store(self, category: str):
        store = MagicMock()
        store.list_by_category.return_value = []
        action = ListServersAction(server_config_store=store)
        _run(action.execute(ListServersInput(category=category)))
        store.list_by_category.assert_called_once_with(category)
