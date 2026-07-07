"""
RagProvider - High-level synchronous interface for RAG service.
"""
import logging
from typing import Optional, Dict, List

from pydantic import HttpUrl

from .client import RagClient
from .models import (
    AvailableTagsResponse,
    AvailableDocsResponse,
    QueryMatchResponse,
)

logger = logging.getLogger(__name__)


class RagProvider:
    """
    High-level synchronous RAG interface.

    Provides a clean API for:
    - Querying vector database
    - Fetching available tags
    - Fetching available documents
    """

    def __init__(
            self,
            base_url: HttpUrl,
            top_k: int = 10,
            timeout: float = 30.0,
            headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize RAG provider.

        Args:
            base_url: RAG service URL
            top_k: Default number of results for queries
            timeout: Request timeout in seconds
            headers: Optional HTTP headers
        """
        self.base_url = base_url
        self.top_k = top_k
        self.timeout = timeout
        self.headers = headers or {}

    def _create_client(self) -> RagClient:
        """Create a new client instance."""
        return RagClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self.headers,
        )

    def query(
            self,
            query: str,
            top_k: Optional[int] = None,
            scope: Optional[str] = None,
            logged_in_user: Optional[str] = None,
            doc_ids: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
    ) -> QueryMatchResponse:
        """
        Query vector database for matching documents.

        Args:
            query: Search query
            top_k: Override default top_k results
            scope: Optional scope filter
            logged_in_user: Optional user context
            doc_ids: Optional list of document IDs to filter by
            tags: Optional list of tags to filter by

        Returns:
            QueryMatchResponse with matches
        """
        with self._create_client() as client:
            return client.query_match(
                query=query,
                top_k_results=top_k or self.top_k,
                scope=scope,
                logged_in_user=logged_in_user,
                doc_ids=doc_ids,
                tags=tags,
            )

    def get_available_tags(
            self,
            limit: int = 50,
            cursor: Optional[str] = None,
            search_regex: Optional[str] = None,
    ) -> AvailableTagsResponse:
        """
        Fetch available tags.

        Args:
            limit: Number of tags per page
            cursor: Pagination cursor
            search_regex: Filter pattern

        Returns:
            AvailableTagsResponse with tags and pagination
        """
        with self._create_client() as client:
            return client.get_available_tags(
                limit=limit,
                cursor=cursor,
                search_regex=search_regex,
            )

    def get_available_docs(
            self,
            limit: int = 50,
            cursor: Optional[str] = None,
            search_regex: Optional[str] = None,
    ) -> AvailableDocsResponse:
        """
        Fetch available documents.

        Args:
            limit: Number of documents per page
            cursor: Pagination cursor
            search_regex: Filter pattern

        Returns:
            AvailableDocsResponse with documents and pagination
        """
        with self._create_client() as client:
            return client.get_available_docs(
                limit=limit,
                cursor=cursor,
                search_regex=search_regex,
            )

    def __repr__(self) -> str:
        return (
            f"RagProvider(base_url='{self.base_url}', "
            f"top_k={self.top_k}, timeout={self.timeout})"
        )
