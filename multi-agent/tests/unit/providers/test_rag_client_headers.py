"""Unit tests for RagClient and RagProvider internal auth header behavior."""
from mas.elements.providers.rag_client.client import RagClient
from mas.elements.providers.rag_client.rag_provider import RagProvider


class TestRagClientAuthHeader:
    """X-Authenticated-User header stamping on RagClient."""

    def test_header_present_when_authenticated_user_provided(self):
        client = RagClient(
            base_url="http://unifai-rag-server:13456",
            authenticated_user="alice",
        )
        assert client._headers["X-Authenticated-User"] == "alice"

    def test_header_absent_when_authenticated_user_empty(self):
        client = RagClient(
            base_url="http://unifai-rag-server:13456",
            authenticated_user="",
        )
        assert "X-Authenticated-User" not in client._headers

    def test_header_absent_when_authenticated_user_not_provided(self):
        client = RagClient(base_url="http://unifai-rag-server:13456")
        assert "X-Authenticated-User" not in client._headers

    def test_does_not_mutate_caller_headers_dict(self):
        shared_headers = {"Custom-Header": "value"}
        RagClient(
            base_url="http://unifai-rag-server:13456",
            headers=shared_headers,
            authenticated_user="alice",
        )
        assert "X-Authenticated-User" not in shared_headers


class TestRagProviderAuthHeader:
    """RagProvider passes authenticated_user through to client."""

    def test_create_client_passes_authenticated_user(self):
        provider = RagProvider(base_url="http://unifai-rag-server:13456")
        client = provider._create_client(authenticated_user="bob")
        assert client._headers["X-Authenticated-User"] == "bob"

    def test_create_client_without_user_has_no_header(self):
        provider = RagProvider(base_url="http://unifai-rag-server:13456")
        client = provider._create_client()
        assert "X-Authenticated-User" not in client._headers

    def test_create_client_does_not_mutate_provider_headers(self):
        provider = RagProvider(
            base_url="http://unifai-rag-server:13456",
            headers={"Existing": "header"},
        )
        provider._create_client(authenticated_user="alice")
        assert "X-Authenticated-User" not in provider.headers


class TestRagClientUntrustedBaseUrl:
    """base_url is user configuration: no identity nor secret outside the stack's services."""

    def test_no_internal_headers_to_untrusted_host(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "s3cret")
        for url in ("https://attacker.example/x", "http://unifai-rag-server.evil.com:13456",
                    "http://unifai-rag-server@evil.com", "http://rag:5000"):
            client = RagClient(base_url=url, authenticated_user="alice")
            assert "X-Authenticated-User" not in client._headers, url
            assert "X-Internal-Auth" not in client._headers, url

    def test_secret_sent_to_the_rag_service(self, monkeypatch):
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "s3cret")
        client = RagClient(base_url="http://unifai-rag-server:13456", authenticated_user="alice")
        assert client._headers["X-Internal-Auth"] == "s3cret"
        assert client._headers["X-Authenticated-User"] == "alice"

    def test_redirects_are_not_followed(self):
        with RagClient(base_url="http://unifai-rag-server:13456") as client:
            assert client._client.follow_redirects is False
