"""Unit tests for GetAvailableDocs/Tags action user_id forwarding."""
from unittest.mock import patch, MagicMock

from mas.actions.providers.rag.get_available_docs.get_available_docs import (
    GetAvailableDocsAction,
    GetAvailableDocsInput,
)
from mas.actions.providers.rag.get_available_tags.get_available_tags import (
    GetAvailableTagsAction,
    GetAvailableTagsInput,
)


class TestGetAvailableDocsActionIdentity:
    """Verify user_id is forwarded as authenticated_user to the provider."""

    @patch(
        "mas.actions.providers.rag.get_available_docs.get_available_docs.RagProviderFactory"
    )
    def test_user_id_forwarded_to_provider(self, mock_factory_cls):
        mock_provider = MagicMock()
        mock_provider.get_available_docs.return_value = MagicMock(
            total=0, documents=[], nextCursor=None, hasMore=False
        )
        mock_factory_cls.return_value.create.return_value = mock_provider

        action = GetAvailableDocsAction()
        action.execute(GetAvailableDocsInput(user_id="alice", limit=10))

        mock_provider.get_available_docs.assert_called_once_with(
            limit=10,
            cursor=None,
            search_regex=None,
            authenticated_user="alice",
        )

    @patch(
        "mas.actions.providers.rag.get_available_docs.get_available_docs.RagProviderFactory"
    )
    def test_empty_user_id_forwarded(self, mock_factory_cls):
        mock_provider = MagicMock()
        mock_provider.get_available_docs.return_value = MagicMock(
            total=0, documents=[], nextCursor=None, hasMore=False
        )
        mock_factory_cls.return_value.create.return_value = mock_provider

        action = GetAvailableDocsAction()
        action.execute(GetAvailableDocsInput(user_id="", limit=50))

        mock_provider.get_available_docs.assert_called_once_with(
            limit=50,
            cursor=None,
            search_regex=None,
            authenticated_user="",
        )


class TestGetAvailableTagsActionIdentity:
    """Verify user_id is forwarded as authenticated_user to the provider."""

    @patch(
        "mas.actions.providers.rag.get_available_tags.get_available_tags.RagProviderFactory"
    )
    def test_user_id_forwarded_to_provider(self, mock_factory_cls):
        mock_provider = MagicMock()
        mock_provider.get_available_tags.return_value = MagicMock(
            total=0, options=[], nextCursor=None, hasMore=False
        )
        mock_factory_cls.return_value.create.return_value = mock_provider

        action = GetAvailableTagsAction()
        action.execute(GetAvailableTagsInput(user_id="bob", limit=25))

        mock_provider.get_available_tags.assert_called_once_with(
            limit=25,
            cursor=None,
            search_regex=None,
            authenticated_user="bob",
        )

    @patch(
        "mas.actions.providers.rag.get_available_tags.get_available_tags.RagProviderFactory"
    )
    def test_empty_user_id_forwarded(self, mock_factory_cls):
        mock_provider = MagicMock()
        mock_provider.get_available_tags.return_value = MagicMock(
            total=0, options=[], nextCursor=None, hasMore=False
        )
        mock_factory_cls.return_value.create.return_value = mock_provider

        action = GetAvailableTagsAction()
        action.execute(GetAvailableTagsInput(user_id="", limit=50))

        mock_provider.get_available_tags.assert_called_once_with(
            limit=50,
            cursor=None,
            search_regex=None,
            authenticated_user="",
        )
