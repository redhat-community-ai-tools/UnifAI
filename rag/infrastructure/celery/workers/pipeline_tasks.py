"""
Pipeline execution Celery task - driving adapter.

This is a thin adapter that:
1. Receives Celery message (source_type, source_data)
2. Translates to domain types (PipelineContext)
3. Delegates to application layer (PipelineExecutor)

Logic is identical to backend/celery_app/tasks/pipeline_tasks.py,
but uses hexagonal architecture components.
"""
from global_utils.celery_app import CeleryApp
from bootstrap.app_container import pipeline_executor, get_pipeline_handler
from core.pipeline.domain.port import PipelineContext
from shared.logger import logger


def build_context(source_type: str, source_data: dict) -> PipelineContext:
    """
    Translate Celery message format → domain PipelineContext.
    
    Logic identical to backend's pipeline_tasks.py lines 24-47:
    - Extract pipeline_id and metadata from source_data
    - Clean metadata (remove pipeline_id, type_data to avoid duplicates)
    - Add type_data from source_data top level
    - Extract source identifiers based on source type
    
    Args:
        source_type: Type of source (SLACK, DOCUMENT, etc.)
        source_data: RegisteredSource data from registration task
        
    Returns:
        PipelineContext ready for executor
        
    Raises:
        ValueError: If pipeline_id or metadata missing, or unsupported source type
    """
    # Extract (same as backend lines 25-26)
    pipeline_id = source_data.get("pipeline_id")
    metadata_dict = source_data.get("metadata")
    
    # Validate (same as backend lines 27-28)
    if not pipeline_id or not metadata_dict:
        raise ValueError("Pipeline ID or metadata not found in source_data")
    
    # Clean metadata copy (same as backend lines 30-33)
    metadata = metadata_dict.copy()
    metadata.pop("pipeline_id", None)
    metadata.pop("type_data", None)
    
    # Get type_data from source_data top level (same as backend line 34)
    payload_type_data = source_data.get("type_data")
    if payload_type_data:
        metadata["type_data"] = payload_type_data
    
    # Extract source identifiers (same as backend lines 36-47)
    if source_type.upper() == "SLACK":
        source_id = metadata.get("channel_id", "")
        source_name = metadata.get("channel_name", "")
    elif source_type.upper() == "DOCUMENT":
        source_id = metadata.get("doc_id", "")
        source_name = metadata.get("doc_name", "")
    else:
        raise ValueError(f"Unsupported source type: {source_type}")
    
    return PipelineContext(
        pipeline_id=pipeline_id,
        source_type=source_type.upper(),
        source_id=source_id,
        source_name=source_name,
        metadata=metadata,
    )


@CeleryApp().app.task(bind=True)
def execute_pipeline_task(self, source_type: str, source_data: dict):
    """
    General pipeline execution task that works with any source type.
    
    This is a thin driving adapter - receives Celery message and delegates
    to application layer. Logic identical to backend's pipeline_tasks.py.
    
    Args:
        source_type: Type of source (SLACK, DOCUMENT, etc.)
        source_data: RegisteredSource data from registration task
            - pipeline_id: str
            - metadata: dict with source-specific fields
            - type_data: optional dict with additional settings
            
    Returns:
        dict with pipeline_id, source_type, status, and result
    """
    try:
        logger.info(f"Starting pipeline execution for {source_type} source: {source_data}")
        
        # Translate (adapter's job - same logic as backend)
        context = build_context(source_type, source_data)
        
        # Delegate to application (hexagonal equivalent of backend's executor.run())
        handler = get_pipeline_handler(source_type)
        result = pipeline_executor().execute(handler, context)
        
        logger.info(f"Pipeline execution completed successfully for {source_type}: {context.pipeline_id}")
        
        # Return result (same structure as backend's PipelineExecutionResult)
        return {
            "pipeline_id": context.pipeline_id,
            "source_type": source_type,
            "status": "success",
            "result": result,
        }
        
    except Exception as e:
        logger.error(f"Pipeline execution failed for {source_type}: {str(e)}", exc_info=True)
        raise

