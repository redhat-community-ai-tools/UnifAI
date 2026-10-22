"""Unit tests for SlackRetriever internal auth header and timeout."""
from unittest.mock import patch, MagicMock

from mas.elements.retrievers.slack.slack_retriever import SlackRetriever


class _FakeIdentity:
    """Minimal RetrievalIdentity for testing."""

    def __init__(self, identity_id="alice"):
        self._identity_id = identity_id

    @property
    def identity_id(self) -> str:
        return self._identity_id


class TestSlackRetrieverAuthHeader:
    """X-Authenticated-User header on outbound requests."""

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_header_sent_when_identity_present(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        identity = _FakeIdentity(identity_id="alice")
        retriever = SlackRetriever(
            api_url="http://unifai-rag-server:13456/api/slack/query.match",
            top_k_results=5,
            threshold=0.5,
            identity=identity,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"X-Authenticated-User": "alice"}
        assert kwargs["allow_redirects"] is False

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_no_internal_headers_to_untrusted_api_url(self, mock_get, monkeypatch):
        """api_url is user configuration: the secret must never leave the stack."""
        monkeypatch.setenv("INTERNAL_AUTH_SECRET", "s3cret")
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()
        retriever = SlackRetriever(
            api_url="https://attacker.example/collect",
            top_k_results=5,
            threshold=0.5,
            identity=_FakeIdentity(identity_id="alice"),
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {}

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_no_header_when_identity_absent(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        retriever = SlackRetriever(
            api_url="http://slack-service:5000/search",
            top_k_results=5,
            threshold=0.5,
            identity=None,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {}

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_no_header_when_identity_id_empty(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        identity = _FakeIdentity(identity_id="")
        retriever = SlackRetriever(
            api_url="http://slack-service:5000/search",
            top_k_results=5,
            threshold=0.5,
            identity=identity,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {}


class TestSlackRetrieverTimeout:
    """Timeout is passed to requests.get."""

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_default_timeout_passed(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        retriever = SlackRetriever(
            api_url="http://slack-service:5000/search",
            top_k_results=5,
            threshold=0.5,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 30.0

    @patch("mas.elements.retrievers.slack.slack_retriever.requests.get")
    def test_custom_timeout_passed(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"search_results": []}),
        )
        mock_get.return_value.raise_for_status = MagicMock()

        retriever = SlackRetriever(
            api_url="http://slack-service:5000/search",
            top_k_results=5,
            threshold=0.5,
            timeout=10.0,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 10.0
