"""Celery adapter for SlackEventDispatcher port."""
import uuid
from typing import Dict, Any

from core.data_sources.types.slack.domain.event.dispatcher import SlackEventDispatcher, SlackEventTaskResult
from global_utils.celery_app.helpers import send_task
from shared.logger import logger


class CelerySlackEventDispatcher(SlackEventDispatcher):
    """
    Celery implementation of SlackEventDispatcher port.
    
    This is a Driven Adapter that implements the domain port
    using Celery for async task dispatch to RabbitMQ.
    """

    # Task name registered in Celery worker (matches rag hexagonal architecture path)
    SLACK_EVENT_TASK = "infrastructure.celery.workers.slack_event_tasks.process_slack_events_task"
    
    # Dedicated queue for Slack events
    QUEUE = "slack_events_queue"

    def dispatch(self, payload: Dict[str, Any]) -> SlackEventTaskResult:
        """
        Dispatch a Slack event payload to Celery for async processing.
        """
        event_id = payload.get("event_id", "unknown")
        event = payload.get("event", {})
        event_type = event.get("type", "unknown")
        task_id = str(uuid.uuid4())

        try:
            send_task(
                task_name=self.SLACK_EVENT_TASK,
                celery_queue=self.QUEUE,
                payload=payload,
            )
            logger.info(f"Enqueued Slack event {event_id} ({event_type}) to Celery")
        except Exception as e:
            logger.error(f"Failed to enqueue Slack event {event_id} to Celery: {e}")
            raise

        return SlackEventTaskResult(
            task_id=task_id,
            queue=self.QUEUE,
            event_id=event_id,
            event_type=event_type,
        )

