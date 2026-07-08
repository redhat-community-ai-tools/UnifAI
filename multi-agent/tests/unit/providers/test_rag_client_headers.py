"""Unit tests for RagClient and RagProvider internal auth header behavior."""
import pytest
from unittest.mock import patch, MagicMock

from mas.elements.providers.rag_client.client import RagClient
from mas.elements.providers.rag_client.rag_provider import RagProvider


class TestRagClientAuthHeader:
    """X-Authenticated-User header stamping on RagClient."""

    def test_header_present_when_authenticated_user_provided(self):
        client = RagClient(
            base_url="http://rag:5000",
            authenticated_user="alice",
        )
        assert client._headers["X-Authenticated-User"] == "alice"

    def test_header_absent_when_authenticated_user_empty(self):
        client = RagClient(
            base_url="http://rag:5000",
            authenticated_user="",
        )
        assert "X-Authenticated-User" not in client._headers

    def test_header_absent_when_authenticated_user_not_provided(self):
        client = RagClient(base_url="http://rag:5000")
        assert "X-Authenticated-User" not in client._headers

    def test_does_not_mutate_caller_headers_dict(self):
        shared_headers = {"Custom-Header": "value"}
        RagClient(
            base_url="http://rag:5000",
            headers=shared_headers,
            authenticated_user="alice",
        )
        assert "X-Authenticated-User" not in shared_headers


class TestRagProviderAuthHeader:
    """RagProvider passes authenticated_user through to client."""

    def test_create_client_passes_authenticated_user(self):
        provider = RagProvider(base_url="http://rag:5000")
        client = provider._create_client(authenticated_user="bob")
        assert client._headers["X-Authenticated-User"] == "bob"

    def test_create_client_without_user_has_no_header(self):
        provider = RagProvider(base_url="http://rag:5000")
        client = provider._create_client()
        assert "X-Authenticated-User" not in client._headers

    def test_create_client_does_not_mutate_provider_headers(self):
        provider = RagProvider(
            base_url="http://rag:5000",
            headers={"Existing": "header"},
        )
        provider._create_client(authenticated_user="alice")
        assert "X-Authenticated-User" not in provider.headers
