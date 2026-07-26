"""Unit tests for RetrievalService (document search)."""
from unittest.mock import create_autospec

import numpy as np
import pytest

from core.retrieval.service import RetrievalService, SearchQuery
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import SearchResult
from core.vector.domain.repository import VectorRepository
from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_embedder():
    embedder = create_autospec(EmbeddingGenerator, instance=True)
    embedder.generate_query_embedding.return_value = np.array([0.1, 0.2, 0.3])
    return embedder


@pytest.fixture
def mock_vector_repo():
    repo = create_autospec(VectorRepository, instance=True)
    repo.search.return_value = []
    return repo


@pytest.fixture
def mock_resolver():
    return create_autospec(SourceFilterResolver, instance=True)


@pytest.fixture
def service(mock_embedder, mock_vector_repo, mock_resolver):
    return RetrievalService(
        embedder=mock_embedder,
        vector_repo=mock_vector_repo,
        filter_resolver=mock_resolver,
        source_type="DOCUMENT",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
@pytest.mark.retrieval
class TestRetrievalService:
    """Tests the RetrievalService search logic: filter resolution, owner_id
    enforcement, embedding generation, and result mapping."""

    def test_search_no_doc_filters(self, service, mock_resolver, mock_vector_repo, mock_embedder):
        """A search with no doc_ids/tags must still enforce metadata.owner_id filter.

        Expected: generate_query_embedding called; filters contain only owner_id.
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test query", owner_id="alice", limit=5)

        mock_embedder.generate_query_embedding.assert_called_once_with("test query")
        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters["metadata.owner_id"] == "alice"

    def test_search_early_exit_empty_filter(self, service, mock_resolver, mock_vector_repo, mock_embedder):
        """When filters resolve to an empty set, search must return [] without generating embeddings.

        Expected: result == [], embedding not generated, vector search not called.
        """
        mock_resolver.resolve.return_value = set()

        result = service.search(query="test", owner_id="alice", limit=5)

        assert result == []
        mock_embedder.generate_query_embedding.assert_not_called()
        mock_vector_repo.search.assert_not_called()

    def test_search_with_doc_ids(self, service, mock_resolver, mock_vector_repo):
        """Passing doc_ids must restrict the search to those specific source IDs plus owner_id.

        Expected: filters contain both metadata.source_id and metadata.owner_id.
        """
        mock_resolver.resolve.return_value = {"src_1", "src_2"}

        service.search(query="test", owner_id="alice", limit=5, doc_ids=["src_1", "src_2"])

        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert set(filters["metadata.source_id"]) == {"src_1", "src_2"}
        assert filters["metadata.owner_id"] == "alice"

    def test_search_owner_id_always_applied(self, service, mock_resolver, mock_vector_repo):
        """owner_id filter is mandatory and always present regardless of other filters.

        Expected: filters['metadata.owner_id'] == 'bob' even with no doc_ids/tags.
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test", owner_id="bob", limit=5)

        call_kwargs = mock_vector_repo.search.call_args
        filters = call_kwargs.kwargs.get("filters") or call_kwargs[1].get("filters")
        assert filters["metadata.owner_id"] == "bob"

    def test_search_resolver_receives_owner_id(self, service, mock_resolver, mock_vector_repo):
        """The resolver must receive owner_id alongside source_type, doc_ids, and tags.

        Expected: resolver.resolve called with owner_id='alice'.
        """
        mock_resolver.resolve.return_value = None

        service.search(query="test", owner_id="alice", limit=5, doc_ids=["d1"], tags=["t1"])

        mock_resolver.resolve.assert_called_once_with(
            source_type="DOCUMENT",
            owner_id="alice",
            doc_ids=["d1"],
            tags=["t1"],
        )

    def test_search_result_mapping(self, service, mock_resolver, mock_vector_repo):
        """SearchResult domain objects must be mapped to plain dicts with id, score, content, metadata.

        Expected: 2 results, first result matches the full expected dict.
        """
        mock_resolver.resolve.return_value = None
        mock_vector_repo.search.return_value = [
            SearchResult(id="r1", score=0.95, content="hello world", metadata={"source_id": "s1"}),
            SearchResult(id="r2", score=0.80, content="foo bar", metadata={"source_id": "s2"}),
        ]

        results = service.search(query="test", owner_id="alice", limit=2)

        assert len(results) == 2
        assert results[0] == {
            "id": "r1",
            "score": 0.95,
            "content": "hello world",
            "metadata": {"source_id": "s1"},
        }
        assert results[1]["id"] == "r2"

    def test_search_with_query_delegates(self, service, mock_resolver, mock_vector_repo):
        """search_with_query must unpack the SearchQuery DTO and delegate to the resolver.

        Expected: resolver.resolve called with source_type, owner_id, doc_ids, and tags from the query.
        """
        mock_resolver.resolve.return_value = None

        query = SearchQuery(
            query_text="find docs",
            source_type="DOCUMENT",
            owner_id="bob",
            top_k=3,
            doc_ids=["d1"],
            tags=["tag1"],
        )
        service.search_with_query(query)

        mock_resolver.resolve.assert_called_once_with(
            source_type="DOCUMENT",
            owner_id="bob",
            doc_ids=["d1"],
            tags=["tag1"],
        )
