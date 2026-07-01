"""Shared fixtures and helpers for RAG unit tests."""
import pytest

from core.pipeline.domain.port import PipelineContext


@pytest.fixture
def build_context():
    """Factory fixture for creating PipelineContext instances with defaults.

    Usage:
        def test_something(self, build_context):
            ctx = build_context(source_name="custom.pdf")
    """
    def _factory(**overrides):
        defaults = dict(
            pipeline_id="pipe_1",
            source_type="DOCUMENT",
            source_id="src_1",
            source_name="report.pdf",
            owner_id="alice",
            metadata={"doc_path": "/tmp/report.pdf", "upload_by": "alice"},
        )
        defaults.update(overrides)
        return PipelineContext(**defaults)
    return _factory
