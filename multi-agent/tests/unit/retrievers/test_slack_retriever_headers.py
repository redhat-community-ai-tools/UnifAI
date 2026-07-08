"""Unit tests for SlackRetriever internal auth header and timeout."""
import pytest
from unittest.mock import patch, MagicMock

from mas.elements.retrievers.slack.slack_retriever import SlackRetriever


class _FakeIdentity:
    """Minimal RetrievalIdentity for testing."""

    def __init__(self, scope="private", identity_id="alice"):
        self._scope = scope
        self._identity_id = identity_id

    @property
    def scope(self) -> str:
        return self._scope

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
            api_url="http://slack-service:5000/search",
            top_k_results=5,
            threshold=0.5,
            identity=identity,
        )
        retriever.retrieve("test query")

        _, kwargs = mock_get.call_args
        assert kwargs["headers"] == {"X-Authenticated-User": "alice"}

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
