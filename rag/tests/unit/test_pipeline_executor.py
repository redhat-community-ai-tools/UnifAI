"""Unit tests for PipelineExecutor orchestration."""
from unittest.mock import MagicMock, create_autospec, PropertyMock

import pytest

from core.pipeline.domain.model import PipelineStatus
from core.pipeline.domain.port import SourcePipelinePort
from core.pipeline.executor import PipelineExecutor
from core.pipeline.service import PipelineService
from core.monitoring.service import MonitoringService
from core.data_sources.service import DataSourceService
from core.vector.domain.repository import VectorRepository


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_pipeline_svc():
    return create_autospec(PipelineService, instance=True)


@pytest.fixture
def mock_monitoring_svc():
    return create_autospec(MonitoringService, instance=True)


@pytest.fixture
def mock_data_source_svc():
    return create_autospec(DataSourceService, instance=True)


@pytest.fixture
def mock_vector_repo():
    return create_autospec(VectorRepository, instance=True)


@pytest.fixture
def mock_handler():
    handler = create_autospec(SourcePipelinePort, instance=True)
    type(handler).source_type = PropertyMock(return_value="DOCUMENT")
    handler.collect.return_value = {"text": "hello"}
    handler.process.return_value = {"text": "processed"}
    handler.chunk_and_embed.return_value = [MagicMock()]
    handler.get_summary.return_value = {"page_count": 1}
    return handler


@pytest.fixture
def executor(mock_pipeline_svc, mock_monitoring_svc, mock_data_source_svc, mock_vector_repo):
    return PipelineExecutor(
        pipeline_service=mock_pipeline_svc,
        monitoring_service=mock_monitoring_svc,
        data_source_service=mock_data_source_svc,
        vector_repository=MagicMock(return_value=mock_vector_repo),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
@pytest.mark.document
@pytest.mark.pipeline
class TestPipelineExecutor:
    """Tests the PipelineExecutor orchestration: status transitions, error handling,
    cleanup guarantees, and monitoring setup."""

    # ── Happy path ────────────────────────────────────────────────────────

    def test_happy_path_status_transitions(
        self, executor, mock_handler, mock_pipeline_svc, build_context,
    ):
        """A successful execution must transition through all statuses in order.

        Expected: COLLECTING → PROCESSING → CHUNKING_AND_EMBEDDING → STORING → DONE.
        Logs: No warnings or errors.
        """
        ctx = build_context()
        executor.execute(mock_handler, ctx)

        status_calls = [
            c.args[1] for c in mock_pipeline_svc.update_status.call_args_list
        ]
        assert status_calls == [
            PipelineStatus.COLLECTING,
            PipelineStatus.PROCESSING,
            PipelineStatus.CHUNKING_AND_EMBEDDING,
            PipelineStatus.STORING,
            PipelineStatus.DONE,
        ]

    def test_happy_path_stores_embeddings(
        self, executor, mock_handler, mock_vector_repo, build_context,
    ):
        """After all pipeline stages succeed, embeddings must be persisted to vector storage.

        Expected: vector_repo.store called once with the generated chunks.
        Logs: No warnings or errors.
        """
        ctx = build_context()
        executor.execute(mock_handler, ctx)

        mock_vector_repo.store.assert_called_once_with(
            mock_handler.chunk_and_embed.return_value
        )

    def test_happy_path_upserts_source_with_summary(
        self, executor, mock_handler, mock_data_source_svc, build_context,
    ):
        """After success, the data source must be upserted with the handler's summary.

        Expected: upsert_after_pipeline called once with all context fields and summary.
        Logs: No warnings or errors.
        """
        ctx = build_context()
        executor.execute(mock_handler, ctx)

        mock_data_source_svc.upsert_after_pipeline.assert_called_once_with(
            source_id="src_1",
            source_name="report.pdf",
            source_type="DOCUMENT",
            pipeline_id="pipe_1",
            summary={"page_count": 1},
        )

    # ── Failure at each handler step (parametrized) ───────────────────────

    @pytest.mark.parametrize("step_method,expected_failed_at,expected_statuses", [
        ("collect", "COLLECTING", [
            PipelineStatus.COLLECTING,
            PipelineStatus.FAILED,
        ]),
        ("process", "PROCESSING", [
            PipelineStatus.COLLECTING,
            PipelineStatus.PROCESSING,
            PipelineStatus.FAILED,
        ]),
        ("chunk_and_embed", "CHUNKING_AND_EMBEDDING", [
            PipelineStatus.COLLECTING,
            PipelineStatus.PROCESSING,
            PipelineStatus.CHUNKING_AND_EMBEDDING,
            PipelineStatus.FAILED,
        ]),
    ])
    def test_failure_at_handler_step_records_error(
        self, executor, mock_handler, mock_monitoring_svc, mock_pipeline_svc,
        build_context, step_method, expected_failed_at, expected_statuses,
    ):
        """When a handler step raises, the error must be recorded with the correct failed_at stage
        and the pipeline status must transition through completed stages then FAILED.

        Expected: record_error called with failed_at matching the step; full status sequence
        includes only stages reached before the failure, followed by FAILED.
        Logs: No warnings or errors (error is recorded via monitoring, not logged to console).
        """
        getattr(mock_handler, step_method).side_effect = RuntimeError("boom")
        ctx = build_context()

        with pytest.raises(RuntimeError, match="boom"):
            executor.execute(mock_handler, ctx)

        mock_monitoring_svc.record_error.assert_called_once()
        error_details = mock_monitoring_svc.record_error.call_args.kwargs.get(
            "error_details"
        ) or mock_monitoring_svc.record_error.call_args[1].get("error_details")
        assert error_details["failed_at"] == expected_failed_at

        status_calls = [
            c.args[1] for c in mock_pipeline_svc.update_status.call_args_list
        ]
        assert status_calls == expected_statuses

    def test_failure_at_store_records_error(
        self, executor, mock_handler, mock_monitoring_svc, mock_pipeline_svc,
        mock_vector_repo, build_context,
    ):
        """When vector storage fails, the error must be recorded with failed_at='STORING'
        and the full status sequence must end with FAILED.

        Expected: error_details['failed_at'] == 'STORING'; status sequence includes all
        stages up to STORING followed by FAILED.
        Logs: No warnings or errors.
        """
        mock_vector_repo.store.side_effect = RuntimeError("store boom")
        ctx = build_context()

        with pytest.raises(RuntimeError, match="store boom"):
            executor.execute(mock_handler, ctx)

        error_details = mock_monitoring_svc.record_error.call_args.kwargs.get(
            "error_details"
        ) or mock_monitoring_svc.record_error.call_args[1].get("error_details")
        assert error_details["failed_at"] == "STORING"

        status_calls = [
            c.args[1] for c in mock_pipeline_svc.update_status.call_args_list
        ]
        assert status_calls == [
            PipelineStatus.COLLECTING,
            PipelineStatus.PROCESSING,
            PipelineStatus.CHUNKING_AND_EMBEDDING,
            PipelineStatus.STORING,
            PipelineStatus.FAILED,
        ]

    # ── Failure upserts error summary ─────────────────────────────────────

    def test_failure_upserts_source_with_error_info(
        self, executor, mock_handler, mock_data_source_svc, build_context,
    ):
        """On failure, the data source must still be upserted with error details in the summary.

        Expected: summary contains 'bad data' in last_error and failed_at='COLLECTING'.
        Logs: No warnings or errors.
        """
        mock_handler.collect.side_effect = ValueError("bad data")
        ctx = build_context()

        with pytest.raises(ValueError):
            executor.execute(mock_handler, ctx)

        upsert_call = mock_data_source_svc.upsert_after_pipeline
        upsert_call.assert_called_once()
        summary = upsert_call.call_args.kwargs.get("summary") or upsert_call.call_args[1].get("summary")
        assert "bad data" in summary["last_error"]
        assert summary["failed_at"] == "COLLECTING"

    # ── Cleanup guarantees ────────────────────────────────────────────────

    def test_cleanup_always_called_on_success(
        self, executor, mock_handler, mock_monitoring_svc, build_context,
    ):
        """Cleanup and monitoring teardown must run even when the pipeline succeeds.

        Expected: handler.cleanup and finish_log_monitoring each called once.
        Logs: No warnings or errors.
        """
        ctx = build_context()
        executor.execute(mock_handler, ctx)

        mock_handler.cleanup.assert_called_once_with(ctx)
        handle = mock_monitoring_svc.start_log_monitoring.return_value
        mock_monitoring_svc.finish_log_monitoring.assert_called_once_with(handle)

    def test_cleanup_always_called_on_failure(
        self, executor, mock_handler, mock_monitoring_svc, build_context,
    ):
        """Cleanup and monitoring teardown must run even when the pipeline fails.

        Expected: handler.cleanup and finish_log_monitoring each called once despite the exception.
        Logs: No warnings or errors.
        """
        mock_handler.collect.side_effect = RuntimeError("fail")
        ctx = build_context()

        with pytest.raises(RuntimeError):
            executor.execute(mock_handler, ctx)

        mock_handler.cleanup.assert_called_once_with(ctx)
        handle = mock_monitoring_svc.start_log_monitoring.return_value
        mock_monitoring_svc.finish_log_monitoring.assert_called_once_with(handle)

    # ── Exception propagation ─────────────────────────────────────────────

    def test_exception_re_raised(self, executor, mock_handler, build_context):
        """Exceptions must not be swallowed -- they must propagate to the caller after cleanup.

        Expected: TypeError('wrong type') is re-raised.
        Logs: No warnings or errors.
        """
        mock_handler.process.side_effect = TypeError("wrong type")
        ctx = build_context()

        with pytest.raises(TypeError, match="wrong type"):
            executor.execute(mock_handler, ctx)

    # ── Monitoring setup ──────────────────────────────────────────────────

    def test_monitoring_started_with_correct_pipeline_id(
        self, executor, mock_handler, mock_monitoring_svc, build_context,
    ):
        """Monitoring must be started with a pipeline_id derived from source_type + source_id.

        Expected: pipeline_id == 'document_src_1' (lowercase source_type + '_' + source_id).
        Logs: No warnings or errors.
        """
        ctx = build_context()
        executor.execute(mock_handler, ctx)

        mock_monitoring_svc.start_log_monitoring.assert_called_once()
        call_kwargs = mock_monitoring_svc.start_log_monitoring.call_args
        pipeline_id_arg = call_kwargs.kwargs.get("pipeline_id") or call_kwargs[1].get("pipeline_id")
        assert pipeline_id_arg == "document_src_1"
