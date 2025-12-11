"""
DataflowClient - Synchronous HTTP client for Dataflow service communication.
"""
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import httpx
from pydantic import HttpUrl

from .models import (
    AvailableTagsResponse,
    AvailableDocsResponse,
    QueryMatchResponse,
    HealthResponse,
)

logger = logging.getLogger(__name__)


class DataflowClientError(Exception):
    """Base error for Dataflow client operations."""
    pass


class DataflowConnectionError(DataflowClientError):
    """Connection-related errors."""
    pass


class DataflowClient:
    """
    Synchronous HTTP client for Dataflow service.

    Provides methods for:
    - Fetching available tags
    - Fetching available documents
    - Querying vector database
    """

    HEALTH_ENDPOINT = "/api/health/"
    TAGS_ENDPOINT = "/api/docs/available.tags.get"
    DOCS_ENDPOINT = "/api/docs/available.docs.get"
    QUERY_ENDPOINT = "/api/docs/query.match"

    def __init__(
            self,
            base_url: HttpUrl,
            timeout: float = 30.0,
            headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize Dataflow client.

        Args:
            base_url: Dataflow server base URL
            timeout: Request timeout in seconds
            headers: Optional HTTP headers
        """
        self._base_url = str(base_url).rstrip("/")
        self._timeout = timeout
        self._headers = headers or {}
        self._client: Optional[httpx.Client] = None

    def __enter__(self) -> "DataflowClient":
        """Establish HTTP client connection."""
        self._client = httpx.Client(
            headers=self._headers,
            timeout=httpx.Timeout(
                connect=10.0,
                read=self._timeout,
                write=10.0,
                pool=10.0,
            ),
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close HTTP client connection."""
        if self._client:
            self._client.close()
        self._client = None

    def _require_connected(self) -> None:
        """Ensure client is connected."""
        if not self._client:
            raise DataflowConnectionError(
                "Not connected. Use 'with' context manager."
            )

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint."""
        return urljoin(self._base_url + "/", endpoint.lstrip("/"))

    def get_available_tags(
            self,
            limit: int = 50,
            cursor: Optional[str] = None,
            search_regex: Optional[str] = None,
    ) -> AvailableTagsResponse:
        """
        Fetch available tags from Dataflow service.

        Args:
            limit: Number of tags per page (default 50)
            cursor: Pagination cursor for subsequent pages
            search_regex: Regex pattern to filter tags

        Returns:
            AvailableTagsResponse with tags and pagination info
        """
        self._require_connected()

        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if search_regex:
            params["search_regex"] = search_regex

        try:
            response = self._client.get(
                self._build_url(self.TAGS_ENDPOINT),
                params=params,
            )
            response.raise_for_status()
            return AvailableTagsResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise DataflowClientError(
                f"Failed to fetch tags: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DataflowConnectionError(f"Connection error: {e}") from e

    def get_available_docs(
            self,
            limit: int = 50,
            cursor: Optional[str] = None,
            search_regex: Optional[str] = None,
    ) -> AvailableDocsResponse:
        """
        Fetch available documents from Dataflow service.

        Args:
            limit: Number of documents per page (default 50)
            cursor: Pagination cursor for subsequent pages
            search_regex: Regex pattern to filter documents

        Returns:
            AvailableDocsResponse with documents and pagination info
        """
        self._require_connected()

        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if search_regex:
            params["search_regex"] = search_regex

        try:
            response = self._client.get(
                self._build_url(self.DOCS_ENDPOINT),
                params=params,
            )
            response.raise_for_status()
            return AvailableDocsResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise DataflowClientError(
                f"Failed to fetch docs: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DataflowConnectionError(f"Connection error: {e}") from e

    def query_match(
            self,
            query: str,
            top_k_results: int = 10,
            scope: Optional[str] = None,
            logged_in_user: Optional[str] = None,
            doc_ids: Optional[List[str]] = None,
            tags: Optional[List[str]] = None,
    ) -> QueryMatchResponse:
        """
        Query vector database for matching documents.

        Args:
            query: Search query string
            top_k_results: Number of top results to return
            scope: Optional scope filter
            logged_in_user: Optional logged-in user context
            doc_ids: Optional list of document IDs to filter by
            tags: Optional list of tags to filter by

        Returns:
            QueryMatchResponse with matching results
        """
        self._require_connected()

        params: Dict[str, Any] = {
            "query": query,
            "top_k_results": top_k_results,
        }
        if scope:
            params["scope"] = scope
        if logged_in_user:
            params["loggedInUser"] = logged_in_user
        if doc_ids:
            params["docIds"] = doc_ids
        if tags:
            params["tags"] = tags

        try:
            response = self._client.get(
                self._build_url(self.QUERY_ENDPOINT),
                params=params,
            )
            response.raise_for_status()
            return QueryMatchResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise DataflowClientError(
                f"Query failed: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DataflowConnectionError(f"Connection error: {e}") from e

    def health_check(self) -> HealthResponse:
        """
        Check Dataflow service health.

        Returns:
            HealthResponse with status and message
        """
        self._require_connected()

        try:
            response = self._client.get(
                self._build_url(self.HEALTH_ENDPOINT),
            )
            response.raise_for_status()
            return HealthResponse.model_validate(response.json())
        except httpx.HTTPStatusError as e:
            raise DataflowClientError(
                f"Health check failed: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DataflowConnectionError(f"Connection error: {e}") from e

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None
