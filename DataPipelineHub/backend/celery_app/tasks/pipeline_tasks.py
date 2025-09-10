from datetime import datetime
import os
import uuid
from pipeline.pipeline_repository import PipelineRepository
from global_utils.helpers.helpers import calculate_date_range
from config.app_config import AppConfig
from global_utils.celery_app import CeleryApp
from pipeline.pipeline_factory import PipelineFactory
from pipeline.pipeline_executor import PipelineExecutor
from shared.source_types import (
    SlackMetadata, DocumentMetadata, SlackTypeData, DocumentTypeData,
    RegisteredSource, RegistrationResponse, PipelineExecutionResult
)
from shared.logger import logger
from config.constants import DataSource, PipelineStatus
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from utils.documents import sanitize_filename

app_config = AppConfig.get_instance()
upload_folder = app_config.upload_folder

# Initialize mongo storage for registration
mongo_storage = get_mongo_storage()

@CeleryApp().app.task(bind=True, max_retries=3, default_retry_delay=30)
def register_sources_task(self, data_list: list, source_type: str, upload_by: str = "default"):
    """
    Registration-only task that processes all data sources, creates pipeline IDs,
    and registers them in the mongo sources collection using upsert_source_summary.
    
    Supports optional user-defined metadata (e.g., settings from frontend) that gets
    stored in the type_data.user_settings field in MongoDB for later retrieval.
    
    Args:
        data_list: List of data sources to register. Each item can optionally contain
                  a 'metadata' field with user-defined settings (dateRange, communityPrivacy, etc.)
        source_type: Type of data source (SLACK, DOCUMENT, etc.)
        upload_by: User who initiated the registration
        
    Returns:
        List of registered sources with their pipeline IDs added
    """
    try:
        logger.info(f"Starting registration for {len(data_list)} {source_type} sources by user {upload_by}")
        
        registered_sources = []
        
        for instance in data_list:
            # Extract optional user-defined metadata from frontend
            user_metadata = instance.get("metadata", {})
            if user_metadata:
                logger.info(f"Processing user metadata: {user_metadata}")
            
            # Generate source_id and pipeline_id based on source type
            if source_type.upper() == DataSource.SLACK.upper_name:
                source_id = instance.get("channel_id", "")
                source_name = instance.get("channel_name", "")
                pipeline_id = f"{DataSource.SLACK.value}_{source_id}"
                
                # Create metadata object
                metadata = SlackMetadata(
                    channel_id=source_id,
                    channel_name=source_name,
                    is_private=instance.get("is_private", False),
                    upload_by=upload_by
                )
                
                date_range = user_metadata.get("dateRange")
                start_datetime, end_datetime = calculate_date_range(date_range)
                
                # Create type_data for Slack using Pydantic model
                slack_type_data = SlackTypeData(
                    is_private=instance.get("is_private", False),
                    start_timestamp=start_datetime,
                    end_timestamp=end_datetime,
                    **user_metadata  # Unpack user metadata into the model
                )
                type_data = slack_type_data.model_dump()
                
            elif source_type.upper() == DataSource.DOCUMENT.upper_name:
                source_id = str(uuid.uuid4())
                source_name = sanitize_filename(instance.get("source_name", ""))
                doc_path = os.path.join(upload_folder, source_name)
                pipeline_id = f"{DataSource.DOCUMENT.value}_{source_id}"
                
                # Create metadata object
                metadata = DocumentMetadata(
                    doc_id=source_id,
                    doc_name=source_name,
                    doc_path=doc_path,
                    upload_by=upload_by
                )
                
                # Create type_data for Document using Pydantic model
                doc_type_data = DocumentTypeData(
                    file_type=source_name.rsplit(".", 1)[-1].lower(),
                    doc_path=doc_path,
                    page_count=0,
                    full_text="",
                    file_size=0,
                    **user_metadata  # Unpack user metadata into the model
                )
                type_data = doc_type_data.model_dump()
                
            else:
                logger.error(f"Unsupported source type: {source_type}")
                continue

            # Register source using upsert_source_summary (only type_data now)
            mongo_storage.upsert_source_summary(
                source_id=source_id,
                source_name=source_name,
                source_type=source_type.upper(),
                upload_by=upload_by,
                pipeline_id=pipeline_id,
                type_data=type_data
            )
            
            # Return only essential data needed for pipeline execution
            registered_source = RegisteredSource(
                pipeline_id=pipeline_id,
                metadata=metadata.__dict__, 
                source_type=source_type.upper(),
                upload_by=upload_by,
                type_data=type_data
            )
            
            registered_sources.append(registered_source.model_dump())
            metadata_info = f" with user settings: {user_metadata}" if user_metadata else ""
            logger.info(f"Registered {source_type} source: {source_name} with pipeline_id: {pipeline_id}{metadata_info}")
        
        logger.info(f"Successfully registered {len(registered_sources)} {source_type} sources with pipeline IDs")
        
        return RegistrationResponse(
            status="registration_complete",
            registered_sources=registered_sources
        ).model_dump()
        
    except Exception as e:
        logger.error(f"Registration task failed for {source_type}: {str(e)}", exc_info=True)
        raise self.retry(exc=e)

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