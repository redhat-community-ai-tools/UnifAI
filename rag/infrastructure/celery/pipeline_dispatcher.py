"""Celery adapter for PipelineTaskDispatcher port."""
import uuid
from typing import Dict, Any, List

from core.pipeline.domain.dispatcher import PipelineTaskDispatcher, TaskResult
from global_utils.celery_app.helpers import send_task
from shared.logger import logger


class CeleryPipelineDispatcher(PipelineTaskDispatcher):
    """
    Celery implementation of PipelineTaskDispatcher port.
    
    This is a Driven Adapter that implements the domain port
    using Celery for async task dispatch to RabbitMQ.
    """

    # Task name registered in Celery worker (matches rag hexagonal architecture path)
    PIPELINE_TASK = "infrastructure.celery.workers.pipeline_tasks.execute_pipeline_task"

    def dispatch(
        self,
        source_type: str,
        source_data: Dict[str, Any],
    ) -> TaskResult:
        """
        Dispatch a single pipeline execution task to Celery.
        
        Routes to source-type-specific queue (e.g., document_queue, slack_queue).
        """
        queue = f"{source_type.lower()}_queue"
        pipeline_id = source_data.get("pipeline_id", "unknown")
        task_id = str(uuid.uuid4())

        try:
            send_task(
                task_name=self.PIPELINE_TASK,
                celery_queue=queue,
                source_type=source_type.upper(),
                source_data=source_data,
            )
            logger.info(f"Dispatched pipeline task {task_id} to {queue} for pipeline {pipeline_id}")
        except Exception as e:
            logger.error(f"Failed to dispatch pipeline task for {pipeline_id}: {e}")
            raise

        return TaskResult(
            task_id=task_id,
            queue=queue,
            source_type=source_type.upper(),
            pipeline_id=pipeline_id,
        )

    def dispatch_batch(
        self,
        source_type: str,
        sources: List[Dict[str, Any]],
    ) -> List[TaskResult]:
        """
        Dispatch multiple pipeline execution tasks.
        
        Each source gets its own task for parallel processing.
        """
        results = []
        for source_data in sources:
            result = self.dispatch(source_type, source_data)
            results.append(result)
        
        logger.info(f"Dispatched {len(results)} pipeline tasks for {source_type}")
        return results

