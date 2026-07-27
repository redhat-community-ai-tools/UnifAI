"""Unit tests for DataSourceService (document-focused)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, create_autospec

import pytest

from core.data_sources.domain.model import DataSource
from core.data_sources.domain.repository import DataSourceRepository
from core.data_sources.service import DataSourceService, DeleteResult
from core.pipeline.domain.model import PipelineRecord, PipelineStatus, PipelineStats
from core.pipeline.domain.repository import PipelineRepository
from core.vector.domain.repository import VectorRepository


def _make_source(**overrides):
    defaults = dict(
        source_id="src_1",
        source_name="report.pdf",
        source_type="DOCUMENT",
        pipeline_id="pipe_1",
        upload_by="alice",
        created_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        last_sync_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        tags=["finance"],
        type_data={"page_count": 10},
    )
    defaults.update(overrides)
    return DataSource(**defaults)


@pytest.fixture
def mock_source_repo():
    return create_autospec(DataSourceRepository, instance=True)


@pytest.fixture
def mock_pipeline_repo():
    return create_autospec(PipelineRepository, instance=True)


@pytest.fixture
def mock_vector_repo():
    return create_autospec(VectorRepository, instance=True)


@pytest.fixture
def service(mock_source_repo, mock_pipeline_repo, mock_vector_repo):
    return DataSourceService(
        source_repo=mock_source_repo,
        pipeline_repo=mock_pipeline_repo,
        vector_repo_factory=MagicMock(return_value=mock_vector_repo),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Delete
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDataSourceServiceDelete:
    """Tests the cascade-delete flow: vectors → pipelines → source record."""

    def test_delete_source_not_found(self, service, mock_source_repo):
        """Deleting a non-existent source must fail with a 'not found' message.

        Expected: success=False, message contains 'not found'.
        Logs: No warnings or errors.
        """
        mock_source_repo.find_by_id.return_value = None

        result = service.delete("missing")

        assert result.success is False
        assert "not found" in result.message

    def test_delete_happy_path(self, service, mock_source_repo, mock_pipeline_repo, mock_vector_repo):
        """Full cascade delete must remove vectors, pipeline records, and the source itself.

        Expected: success=True, vectors_deleted=5, pipelines_deleted=1, source_deleted=True.
        Logs: No warnings or errors.
        """
        source = _make_source()
        mock_source_repo.find_by_id.return_value = source
        mock_vector_repo.delete_by_source_id.return_value = 5
        mock_pipeline_repo.delete.return_value = 1
        mock_source_repo.delete.return_value = True

        result = service.delete("src_1")

        assert result.success is True
        assert result.vectors_deleted == 5
        assert result.pipelines_deleted == 1
        assert result.source_deleted is True

    def test_delete_vector_failure_aborts(self, service, mock_source_repo, mock_vector_repo):
        """When vector storage (Qdrant) is down, deletion must abort and report the failure.

        Expected: success=False, message contains 'Vector storage'.
        Logs: No warnings or errors.
        """
        source = _make_source()
        mock_source_repo.find_by_id.return_value = source
        mock_vector_repo.delete_by_source_id.side_effect = RuntimeError("qdrant down")

        result = service.delete("src_1")

        assert result.success is False
        assert "Vector storage" in result.message

    def test_delete_mongo_failure_partial(self, service, mock_source_repo, mock_pipeline_repo, mock_vector_repo):
        """When MongoDB fails after vectors are deleted, the result must report partial deletion.

        Expected: success=False, vectors_deleted=3, message contains 'Partial deletion'.
        Logs: No warnings or errors.
        """
        source = _make_source()
        mock_source_repo.find_by_id.return_value = source
        mock_vector_repo.delete_by_source_id.return_value = 3
        mock_pipeline_repo.delete.side_effect = RuntimeError("mongo down")

        result = service.delete("src_1")

        assert result.success is False
        assert result.vectors_deleted == 3
        assert "Partial deletion" in result.message

    def test_delete_uses_correct_collection_name(self, service, mock_source_repo, mock_vector_repo):
        """The vector repo factory must be called with the correct collection name for DOCUMENT type.

        Expected: factory called with 'document_data'.
        Logs: No warnings or errors.
        """
        source = _make_source(source_type="DOCUMENT")
        mock_source_repo.find_by_id.return_value = source
        mock_vector_repo.delete_by_source_id.return_value = 0
        mock_source_repo.delete.return_value = True

        service.delete("src_1")

        factory = service._vector_repo_factory
        factory.assert_called_with("document_data")


# ═══════════════════════════════════════════════════════════════════════════════
# Upsert after pipeline
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDataSourceServiceUpsert:
    """Tests the upsert-after-pipeline flow that creates or updates a data source record."""

    def test_upsert_creates_new_source(self, service, mock_source_repo):
        """When no existing source matches the pipeline, a new DataSource must be created and saved.

        Expected: save called once with source_id='src_new' and type_data from the summary.
        Logs: No warnings or errors.
        """
        mock_source_repo.find_by_pipeline_id.return_value = None

        service.upsert_after_pipeline(
            source_id="src_new",
            source_name="new.pdf",
            source_type="DOCUMENT",
            pipeline_id="pipe_new",
            summary={"page_count": 3},
        )

        mock_source_repo.save.assert_called_once()
        saved = mock_source_repo.save.call_args[0][0]
        assert saved.source_id == "src_new"
        assert saved.type_data == {"page_count": 3}

    def test_upsert_updates_existing_source(self, service, mock_source_repo):
        """When an existing source matches the pipeline, its type_data must be merged (not replaced)
        and last_sync_at must be refreshed.

        Expected: existing type_data keeps page_count=5, gains full_text='updated'; last_sync_at updated.
        Logs: No warnings or errors.
        """
        existing = _make_source(type_data={"page_count": 5})
        old_sync = existing.last_sync_at
        mock_source_repo.find_by_pipeline_id.return_value = existing

        service.upsert_after_pipeline(
            source_id="src_1",
            source_name="report.pdf",
            source_type="DOCUMENT",
            pipeline_id="pipe_1",
            summary={"full_text": "updated"},
        )

        mock_source_repo.save.assert_called_once()
        assert existing.last_sync_at >= old_sync
        assert existing.type_data["full_text"] == "updated"
        assert existing.type_data["page_count"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Enrich with pipeline stats
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDataSourceServiceEnrich:
    """Tests enriching data source listings with pipeline statistics."""

    def test_enrich_empty_list(self, service):
        """Enriching an empty list must return an empty list without calling the repo.

        Expected: result == [].
        Logs: No warnings or errors.
        """
        result = service.enrich_with_pipeline_stats([])
        assert result == []

    def test_enrich_with_pipeline_stats(self, service, mock_pipeline_repo):
        """When a matching pipeline record exists, its status and stats must be injected.

        Expected: status='DONE', chunks_generated=10.
        Logs: No warnings or errors.
        """
        source = _make_source()
        record = PipelineRecord(
            pipeline_id="pipe_1",
            source_type="DOCUMENT",
            status=PipelineStatus.DONE,
            created_at=datetime(2025, 1, 1),
            last_updated=datetime(2025, 1, 2),
            stats=PipelineStats(documents_retrieved=1, chunks_generated=10),
        )
        mock_pipeline_repo.get_stats_batch.return_value = {"pipe_1": record}

        result = service.enrich_with_pipeline_stats([source])

        assert len(result) == 1
        assert result[0]["status"] == "DONE"
        assert result[0]["pipeline_stats"]["chunks_generated"] == 10

    def test_enrich_without_pipeline_stats(self, service, mock_pipeline_repo):
        """When no pipeline record exists for a source, status and stats must be None.

        Expected: status=None, pipeline_stats=None.
        Logs: No warnings or errors.
        """
        source = _make_source()
        mock_pipeline_repo.get_stats_batch.return_value = {}

        result = service.enrich_with_pipeline_stats([source])

        assert result[0]["status"] is None
        assert result[0]["pipeline_stats"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Update
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
class TestDataSourceServiceUpdate:
    """Tests partial updates to existing data source records."""

    def test_update_existing_source(self, service, mock_source_repo):
        """Updating an existing source must apply the fields and persist.

        Expected: result is True, source_name changed to 'renamed.pdf', save called.
        Logs: No warnings or errors.
        """
        source = _make_source()
        mock_source_repo.find_by_id.return_value = source

        result = service.update("src_1", {"source_name": "renamed.pdf"})

        assert result is True
        assert source.source_name == "renamed.pdf"
        mock_source_repo.save.assert_called_once()

    def test_update_nonexistent_source(self, service, mock_source_repo):
        """Updating a non-existent source must return False without saving.

        Expected: result is False, save not called.
        Logs: No warnings or errors.
        """
        mock_source_repo.find_by_id.return_value = None

        result = service.update("missing", {"source_name": "x"})

        assert result is False
        mock_source_repo.save.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# list_with_stats — upload_by scoping
# ═══════════════════════════════════════════════════════════════════════════════

class TestListWithStatsScoping:

    @pytest.mark.unit
    def test_upload_by_forwarded_to_repository(self, service, mock_source_repo):
        """upload_by must be passed through to repository find_all."""
        mock_source_repo.find_all.return_value = []

        service.list_with_stats("DOCUMENT", upload_by="alice")

        mock_source_repo.find_all.assert_called_once()
        call_kwargs = mock_source_repo.find_all.call_args[1]
        assert call_kwargs["upload_by"] == "alice"

    @pytest.mark.unit
    def test_upload_by_none_passes_none(self, service, mock_source_repo):
        """When upload_by is not provided, None is passed to repository."""
        mock_source_repo.find_all.return_value = []

        service.list_with_stats("DOCUMENT")

        call_kwargs = mock_source_repo.find_all.call_args[1]
        assert call_kwargs["upload_by"] is None
