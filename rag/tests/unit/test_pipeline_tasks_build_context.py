"""Unit tests for build_context() Celery message → PipelineContext translation."""
import pytest

from infrastructure.celery.workers.pipeline_tasks import build_context


class TestBuildContextValidation:
    """Validation branches in build_context()."""

    def test_missing_pipeline_id_raises(self):
        source_data = {"metadata": {"doc_id": "d1", "upload_by": "alice"}}
        with pytest.raises(ValueError, match="Pipeline ID or metadata not found"):
            build_context("DOCUMENT", source_data)

    def test_missing_metadata_raises(self):
        source_data = {"pipeline_id": "pipe_1"}
        with pytest.raises(ValueError, match="Pipeline ID or metadata not found"):
            build_context("DOCUMENT", source_data)

    def test_empty_metadata_raises(self):
        source_data = {"pipeline_id": "pipe_1", "metadata": {}}
        with pytest.raises(ValueError, match="Pipeline ID or metadata not found"):
            build_context("DOCUMENT", source_data)

    def test_missing_owner_id_raises(self):
        source_data = {
            "pipeline_id": "pipe_1",
            "metadata": {"doc_id": "d1", "doc_name": "report.pdf"},
        }
        with pytest.raises(ValueError, match="owner_id.*upload_by.*required"):
            build_context("DOCUMENT", source_data)

    def test_unsupported_source_type_raises(self):
        source_data = {
            "pipeline_id": "pipe_1",
            "upload_by": "alice",
            "metadata": {"some_field": "value"},
        }
        with pytest.raises(ValueError, match="Unsupported source type"):
            build_context("UNKNOWN_TYPE", source_data)


class TestBuildContextHappyPath:
    """Happy-path extraction for supported source types."""

    def test_document_source_type(self):
        source_data = {
            "pipeline_id": "pipe_42",
            "upload_by": "alice",
            "metadata": {
                "doc_id": "doc_99",
                "doc_name": "quarterly.pdf",
                "extra_field": "preserved",
            },
        }

        ctx = build_context("document", source_data)

        assert ctx.pipeline_id == "pipe_42"
        assert ctx.source_type == "DOCUMENT"
        assert ctx.source_id == "doc_99"
        assert ctx.source_name == "quarterly.pdf"
        assert ctx.owner_id == "alice"
        assert ctx.metadata["extra_field"] == "preserved"

    def test_slack_source_type(self):
        source_data = {
            "pipeline_id": "pipe_7",
            "upload_by": "bob",
            "metadata": {
                "channel_id": "C12345",
                "channel_name": "general",
            },
        }

        ctx = build_context("SLACK", source_data)

        assert ctx.pipeline_id == "pipe_7"
        assert ctx.source_type == "SLACK"
        assert ctx.source_id == "C12345"
        assert ctx.source_name == "general"
        assert ctx.owner_id == "bob"

    def test_owner_id_from_metadata_fallback(self):
        source_data = {
            "pipeline_id": "pipe_1",
            "metadata": {
                "doc_id": "d1",
                "doc_name": "file.txt",
                "upload_by": "charlie",
            },
        }

        ctx = build_context("DOCUMENT", source_data)

        assert ctx.owner_id == "charlie"

    def test_type_data_merged_into_metadata(self):
        source_data = {
            "pipeline_id": "pipe_1",
            "upload_by": "alice",
            "metadata": {"doc_id": "d1", "doc_name": "f.txt"},
            "type_data": {"chunk_size": 512},
        }

        ctx = build_context("DOCUMENT", source_data)

        assert ctx.metadata["type_data"] == {"chunk_size": 512}

    def test_metadata_cleaned_of_pipeline_id_and_type_data(self):
        source_data = {
            "pipeline_id": "pipe_1",
            "upload_by": "alice",
            "metadata": {
                "doc_id": "d1",
                "doc_name": "f.txt",
                "pipeline_id": "should_be_removed",
                "type_data": "should_be_removed",
            },
        }

        ctx = build_context("DOCUMENT", source_data)

        assert "pipeline_id" not in ctx.metadata
        assert ctx.metadata.get("type_data") is None or ctx.metadata.get("type_data") != "should_be_removed"
