"""Unit tests for user-level isolation in DocumentService.

Asserts that upload_by is correctly forwarded to the repository and that
only the requested owner's DONE documents/tags are returned.
"""
from datetime import datetime
from unittest.mock import create_autospec, MagicMock

from core.data_sources.types.document.document_service import DocumentService
from core.data_sources.service import DataSourceService
from core.data_sources.domain.repository import DataSourceRepository
from core.data_sources.domain.model import DataSource
from core.pagination.domain.model import PaginatedResult


def _make_source(source_id, name, upload_by, tags=None):
    return DataSource(
        source_id=source_id,
        source_name=name,
        source_type="DOCUMENT",
        pipeline_id=f"pipe_{source_id}",
        upload_by=upload_by,
        created_at=datetime(2026, 1, 1),
        tags=tags or [],
    )


def _enriched_dict(source: DataSource, status="DONE"):
    """Simulate enrichment output (dict with status added)."""
    d = source.to_dict()
    d["status"] = status
    return d


class TestListAvailableDocsUserIsolation:
    """upload_by forwarded to find_paginated; only owner's docs returned."""

    def setup_method(self):
        self.repo = create_autospec(DataSourceRepository)
        self.data_source_service = MagicMock(spec=DataSourceService)
        self.service = DocumentService(
            data_source_service=self.data_source_service,
            source_repo=self.repo,
        )

    def test_upload_by_forwarded_to_repo(self):
        self.repo.find_paginated.return_value = PaginatedResult(
            data=[], next_cursor=None, has_more=False, total=0
        )
        self.data_source_service.enrich_with_pipeline_stats.return_value = []

        self.service.list_available_docs(upload_by="alice")

        self.repo.find_paginated.assert_called_once_with(
            cursor=None,
            limit=50,
            source_type="DOCUMENT",
            search=None,
            upload_by="alice",
        )

    def test_only_done_docs_for_owner_returned(self):
        alice_doc = _make_source("d1", "alice_report.pdf", "alice")

        self.repo.find_paginated.return_value = PaginatedResult(
            data=[alice_doc.to_dict()],
            next_cursor=None, has_more=False, total=1,
        )
        self.data_source_service.enrich_with_pipeline_stats.return_value = [
            _enriched_dict(alice_doc, status="DONE"),
        ]

        result = self.service.list_available_docs(upload_by="alice")

        assert len(result.data) == 1
        assert result.data[0]["id"] == "d1"
        assert result.data[0]["upload_by"] == "alice"

    def test_non_done_docs_excluded(self):
        doc_done = _make_source("d1", "done.pdf", "alice")
        doc_pending = _make_source("d2", "pending.pdf", "alice")

        self.repo.find_paginated.return_value = PaginatedResult(
            data=[doc_done.to_dict(), doc_pending.to_dict()],
            next_cursor=None, has_more=False, total=2,
        )
        self.data_source_service.enrich_with_pipeline_stats.return_value = [
            _enriched_dict(doc_done, status="DONE"),
            _enriched_dict(doc_pending, status="PENDING"),
        ]

        result = self.service.list_available_docs(upload_by="alice")

        assert len(result.data) == 1
        assert result.data[0]["id"] == "d1"


class TestGetAvailableTagsUserIsolation:
    """upload_by forwarded to find_all; only owner's tags returned."""

    def setup_method(self):
        self.repo = create_autospec(DataSourceRepository)
        self.data_source_service = MagicMock(spec=DataSourceService)
        self.service = DocumentService(
            data_source_service=self.data_source_service,
            source_repo=self.repo,
        )

    def test_upload_by_forwarded_to_repo(self):
        self.repo.find_all.return_value = []
        self.data_source_service.enrich_with_pipeline_stats.return_value = []

        self.service.get_available_tags(upload_by="alice")

        self.repo.find_all.assert_called_once_with(
            source_type="DOCUMENT",
            upload_by="alice",
        )

    def test_only_tags_from_owner_done_docs(self):
        alice_doc = _make_source("d1", "a.pdf", "alice", tags=["finance", "q1"])

        self.repo.find_all.return_value = [alice_doc]
        self.data_source_service.enrich_with_pipeline_stats.return_value = [
            _enriched_dict(alice_doc, status="DONE"),
        ]

        result = self.service.get_available_tags(upload_by="alice")

        tag_values = {t["value"] for t in result.data}
        assert tag_values == {"finance", "q1"}

    def test_tags_from_non_done_docs_excluded(self):
        doc_done = _make_source("d1", "a.pdf", "alice", tags=["visible"])
        doc_pending = _make_source("d2", "b.pdf", "alice", tags=["hidden"])

        self.repo.find_all.return_value = [doc_done, doc_pending]
        self.data_source_service.enrich_with_pipeline_stats.return_value = [
            _enriched_dict(doc_done, status="DONE"),
            _enriched_dict(doc_pending, status="PENDING"),
        ]

        result = self.service.get_available_tags(upload_by="alice")

        tag_values = {t["value"] for t in result.data}
        assert "visible" in tag_values
        assert "hidden" not in tag_values

    def test_no_cross_user_tags_when_upload_by_set(self):
        """Repo filters by upload_by, so bob's docs never reach the service."""
        alice_doc = _make_source("d1", "a.pdf", "alice", tags=["alice-tag"])

        self.repo.find_all.return_value = [alice_doc]
        self.data_source_service.enrich_with_pipeline_stats.return_value = [
            _enriched_dict(alice_doc, status="DONE"),
        ]

        result = self.service.get_available_tags(upload_by="alice")

        tag_values = {t["value"] for t in result.data}
        assert tag_values == {"alice-tag"}
