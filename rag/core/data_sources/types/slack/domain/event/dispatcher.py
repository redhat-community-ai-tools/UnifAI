"""Slack event task dispatcher port (interface)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass
class SlackEventTaskResult:
    """Result of dispatching a Slack event task."""
    task_id: str
    queue: str
    event_id: str
    event_type: str
    dispatched_at: datetime = None

    def __post_init__(self):
        if self.dispatched_at is None:
            self.dispatched_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "queue": self.queue,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "dispatched_at": self.dispatched_at.isoformat() if self.dispatched_at else None,
        }


class SlackEventDispatcher(ABC):
    """
    Port for dispatching Slack events to async workers.
    
    This is a Driven Port (secondary/output) - the application drives
    external task queues through this interface without knowing the
    implementation details (Celery, SQS, Redis Queue, etc.).
    
    Separate from PipelineTaskDispatcher because:
    - Different purpose (event processing vs pipeline execution)
    - Different queue (slack_events_queue)
    - Single responsibility principle
    """

    @abstractmethod
    def dispatch(self, payload: Dict[str, Any]) -> SlackEventTaskResult:
        """
        Dispatch a Slack event payload for async processing.
        
        Args:
            payload: Full Slack event payload from Events API
            
        Returns:
            SlackEventTaskResult with dispatch details
        """
        ...

