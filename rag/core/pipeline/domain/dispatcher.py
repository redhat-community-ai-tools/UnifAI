"""Pipeline task dispatcher port (interface)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List


@dataclass
class TaskResult:
    """Result of dispatching an async pipeline task."""
    task_id: str
    queue: str
    source_type: str
    pipeline_id: str
    dispatched_at: datetime = None

    def __post_init__(self):
        if self.dispatched_at is None:
            self.dispatched_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "queue": self.queue,
            "source_type": self.source_type,
            "pipeline_id": self.pipeline_id,
            "dispatched_at": self.dispatched_at.isoformat() if self.dispatched_at else None,
        }


class PipelineTaskDispatcher(ABC):
    """
    Port for dispatching pipeline execution tasks to async workers.
    
    This is a Driven Port (secondary/output) - the application drives
    external task queues through this interface without knowing the
    implementation details (Celery, SQS, Redis Queue, etc.).
    """

    @abstractmethod
    def dispatch(
        self,
        source_type: str,
        source_data: Dict[str, Any],
    ) -> TaskResult:
        """
        Dispatch a single pipeline execution task.
        
        Args:
            source_type: Type of source (DOCUMENT, SLACK, etc.)
            source_data: Registered source data containing pipeline_id and metadata
            
        Returns:
            TaskResult with dispatch details
        """
        ...

    @abstractmethod
    def dispatch_batch(
        self,
        source_type: str,
        sources: List[Dict[str, Any]],
    ) -> List[TaskResult]:
        """
        Dispatch multiple pipeline execution tasks.
        
        Args:
            source_type: Type of source (DOCUMENT, SLACK, etc.)
            sources: List of registered source data
            
        Returns:
            List of TaskResult for each dispatched task
        """
        ...

