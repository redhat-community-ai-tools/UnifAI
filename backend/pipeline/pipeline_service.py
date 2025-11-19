from typing import List, Dict, Any, Tuple
from shared.logger import logger
from global_utils.celery_app.helpers import send_task

class PipelineCeleryService:
    """
    Service class for dispatching pipeline execution to Celery workers for
    already-registered sources.
    """

    def execute_pipeline(self, registered_sources: List[Dict[str, Any]], source_type: str) -> Tuple[Dict[str, Any], int]:
        """
        Dispatch pipeline execution tasks to Celery for already-registered sources.
        Returns response data and HTTP status code.
        """
        try:
            pipeline_worker_tasks_submitted = self._dispatch_pipeline_worker_tasks(registered_sources, source_type)

            response_data = {
                "status": "pipeline_workflow_started",
                "message": f"Pipeline started for {len(registered_sources)} {source_type} sources",
                "pipeline_worker_tasks_submitted": pipeline_worker_tasks_submitted,
                "source_count": len(registered_sources),
            }
            return response_data, 202

        except Exception as e:
            logger.error(f"Failed to dispatch pipeline worker tasks: {str(e)}")
            raise e
    
    def _dispatch_pipeline_worker_tasks(self, registered_sources: List[Dict[str, Any]], source_type: str) -> int:
        """
        Dispatch pipeline execution tasks to appropriate Celery worker queues for registered sources.
        Routes tasks to specialized worker queues based on source type for optimal processing.
        
        Args:
            registered_sources: List of registered source data from previous Celery worker results
            source_type: Type of data source for Celery worker queue routing
            
        Returns:
            Number of pipeline worker tasks successfully dispatched to Celery queues
        """
        pipeline_worker_tasks_submitted = 0
        
        for source_data in registered_sources:
            send_task(
                task_name="celery_app.tasks.pipeline_tasks.execute_pipeline_task",
                celery_queue=f"{source_type.lower()}_queue",
                source_type=source_type.upper(),
                source_data=source_data
            )
            pipeline_worker_tasks_submitted += 1
            
        return pipeline_worker_tasks_submitted 