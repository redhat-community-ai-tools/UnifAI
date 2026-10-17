"""Pipeline Executor - Application use case for orchestrating pipeline execution."""
from typing import Any, Callable

from core.pipeline.domain.port import SourcePipelinePort, PipelineContext
from core.pipeline.domain.model import PipelineStatus
from core.vector.domain.repository import VectorRepository
from core.pipeline.service import PipelineService
from core.monitoring.service import MonitoringService
from core.data_sources.service import DataSourceService
from global_utils.telemetry import counter, histogram, start_span
import logging
import time

logger = logging.getLogger("rag_pipeline")

_TRACER = "rag.pipeline"
_pipeline_duration = histogram(
    "rag.pipeline.duration", unit="s", description="Ingestion pipeline duration", meter_name=_TRACER,
)
_stored_embeddings = counter(
    "rag.pipeline.embeddings.stored", unit="{chunk}",
    description="Embedded chunks stored by ingestion pipelines", meter_name=_TRACER,
)


class PipelineExecutor:
    """
    Application use case: orchestrates pipeline execution.
    
    This executor is source-agnostic and delegates source-specific behavior
    to the injected SourcePipelinePort handler.
    
    Responsibilities:
    - Pipeline registration and status tracking
    - Log monitoring (orchestration)
    - Error recording on failure
    - Source upsert on success/failure
    - Cleanup
    
    Usage:
        executor = pipeline_executor()  # from app_container
        handler = get_pipeline_handler("SLACK")
        context = PipelineContext(...)
        result = executor.execute(handler, context)
    """
    
    def __init__(
        self,
        pipeline_service: PipelineService,
        monitoring_service: MonitoringService,
        data_source_service: DataSourceService,
        vector_repository: Callable[[str], VectorRepository],
    ):
        """
        Initialize the pipeline executor.
        
        Args:
            pipeline_service: Service for pipeline CRUD and status tracking
            monitoring_service: Service for log monitoring and error recording
            data_source_service: Service for source upsert operations
            vector_repository: Callable that returns a VectorRepository for a collection name
        """
        self._pipeline_svc = pipeline_service
        self._monitoring_svc = monitoring_service
        self._data_source_svc = data_source_service
        self._vector_repository = vector_repository
    
    def execute(
        self, 
        handler: SourcePipelinePort, 
        context: PipelineContext
    ) -> Any:
        """
        Execute pipeline using the provided source handler.
        
        Args:
            handler: Source-specific pipeline handler implementing SourcePipelinePort
            context: Pipeline execution context with all required metadata
            
        Returns:
            Result from the storage step (typically count of stored embeddings)
            
        Raises:
            Exception: Re-raises any exception after recording error and cleanup
        """
        source_type = handler.source_type
        start = time.perf_counter()
        outcome = "error"
        # Identifiers are internal object ids; no source names or content.
        with start_span(
            "rag.pipeline",
            {
                "rag.source_type": source_type,
                "rag.pipeline.id": context.pipeline_id,
                "rag.source.id": context.source_id,
            },
            tracer_name=_TRACER,
        ) as span:
            try:
                result = self._execute(handler, context)
                outcome = "ok"
            finally:
                _pipeline_duration.record(
                    time.perf_counter() - start,
                    {"rag.source_type": source_type, "rag.outcome": outcome},
                )
            if isinstance(result, int) and not isinstance(result, bool):
                span.set_attribute("rag.pipeline.embeddings.stored", result)
                _stored_embeddings.add(result, {"rag.source_type": source_type})
            return result

    def _execute(
        self,
        handler: SourcePipelinePort,
        context: PipelineContext,
    ) -> Any:
        source_type = handler.source_type
        vector_repo = self._vector_repository(f"{source_type.lower()}_data")
        
        # Register pipeline
        self._pipeline_svc.register(context.pipeline_id, source_type)
        
        # Start log monitoring (orchestration)
        monitoring_pipeline_id = f"{source_type.lower()}_{context.source_id}"
        monitoring_handle = self._monitoring_svc.start_log_monitoring(
            pipeline_id=monitoring_pipeline_id,
            target_logger=logger,
        )
        
        collected = None
        current_step = None
        
        try:
            # Step 1: Collect
            current_step = PipelineStatus.COLLECTING
            self._pipeline_svc.update_status(context.pipeline_id, current_step)
            with start_span("rag.pipeline.collect", tracer_name=_TRACER):
                collected = handler.collect(context)
            
            # Step 2: Process
            current_step = PipelineStatus.PROCESSING
            self._pipeline_svc.update_status(context.pipeline_id, current_step)
            with start_span("rag.pipeline.process", tracer_name=_TRACER):
                processed = handler.process(context, collected)
            
            # Step 3: Chunk & Embed
            current_step = PipelineStatus.CHUNKING_AND_EMBEDDING
            self._pipeline_svc.update_status(context.pipeline_id, current_step)
            with start_span("rag.pipeline.chunk_and_embed", tracer_name=_TRACER):
                embeddings = handler.chunk_and_embed(context, processed)
            
            # Step 4: Store
            current_step = PipelineStatus.STORING
            self._pipeline_svc.update_status(context.pipeline_id, current_step)
            with start_span("rag.pipeline.store", tracer_name=_TRACER):
                result = vector_repo.store(embeddings)
            
            # Success - update status
            self._pipeline_svc.update_status(context.pipeline_id, PipelineStatus.DONE)
            
            # Upsert source with summary
            summary = handler.get_summary(context, collected)
            self._data_source_svc.upsert_after_pipeline(
                source_id=context.source_id,
                source_name=context.source_name,
                source_type=source_type,
                pipeline_id=context.pipeline_id,
                summary=summary,
            )
            
            return result
            
        except Exception as e:
            # Record error
            self._monitoring_svc.record_error(
                pipeline_id=context.pipeline_id,
                error_message=str(e),
                error_details={"failed_at": current_step.value if current_step else "UNKNOWN"},
            )
            
            # Update status to failed
            self._pipeline_svc.update_status(context.pipeline_id, PipelineStatus.FAILED)
            
            # Upsert source with error info
            self._data_source_svc.upsert_after_pipeline(
                source_id=context.source_id,
                source_name=context.source_name,
                source_type=source_type,
                pipeline_id=context.pipeline_id,
                summary={
                    "last_error": str(e),
                    "failed_at": current_step.value if current_step else "UNKNOWN",
                },
            )
            
            raise
            
        finally:
            # Always cleanup: stop monitoring and run handler cleanup
            self._monitoring_svc.finish_log_monitoring(monitoring_handle)
            handler.cleanup(context)
