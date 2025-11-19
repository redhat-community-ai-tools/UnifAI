from pipeline.pipeline_repository import PipelineRepository
from global_utils.celery_app import CeleryApp
from pipeline.pipeline_factory import PipelineFactory
from pipeline.pipeline_executor import PipelineExecutor
from shared.source_types import (
    SlackMetadata, DocumentMetadata,
    PipelineExecutionResult
)
from shared.logger import logger
from config.constants import DataSource

@CeleryApp().app.task(bind=True)
def execute_pipeline_task(self, source_type: str, source_data: dict):
    """
    General pipeline execution task that works with any source type.
    
    Args:
        source_type: Type of source (SLACK, DOCUMENT, etc.)
        source_data: RegisteredSource data from registration task
    """
    try:
        logger.info(f"Starting pipeline execution for {source_type} source: {source_data}")
        
        # Extract data from the clean structure
        pipeline_id = source_data.get("pipeline_id")
        metadata_dict = source_data.get("metadata")
        if not pipeline_id or not metadata_dict:
            raise ValueError("Pipeline ID or metadata not found in source_data")

        metadata_dict_copy = metadata_dict.copy()
        metadata_dict_copy.pop('pipeline_id', None)
        # Remove any existing type_data to avoid passing duplicate keyword arguments
        metadata_dict_copy.pop('type_data', None)
        payload_type_data = source_data.get("type_data")
        
        if source_type.upper() == DataSource.SLACK.upper_name:
            metadata = SlackMetadata(
                **metadata_dict_copy,
                pipeline_id=pipeline_id,
                type_data=payload_type_data
            )
            
        elif source_type.upper() == DataSource.DOCUMENT.upper_name:
            metadata = DocumentMetadata(**metadata_dict_copy, pipeline_id=pipeline_id)
            logger.info(f"Document path: {metadata}")
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
        
        # Create factory and executor using the modular pipeline architecture
        factory = PipelineFactory.create(source_type)
        pipeline = factory.create_pipeline(metadata)
        executor = PipelineExecutor(pipeline, PipelineRepository())
        
        # Execute the pipeline
        result = executor.run()
        
        logger.info(f"Pipeline execution completed successfully for {source_type}: {pipeline_id}")
        return PipelineExecutionResult(
            pipeline_id=pipeline_id,
            source_type=source_type,
            status="success",
            result=result
        ).model_dump()
        
    except Exception as e:
        logger.error(f"Pipeline execution failed for {source_type}: {str(e)}", exc_info=True)