"""
Slack event processing Celery task - driving adapter.

This is a thin adapter that:
1. Receives Celery message (Slack event payload)
2. Delegates to application layer (SlackEventService)

Logic identical to backend/celery_app/tasks/slack_event_subscription_tasks.py,
but uses hexagonal architecture components.
"""
from typing import Dict, Any

from global_utils.celery_app import CeleryApp
from bootstrap.app_container import slack_event_service
from shared.logger import logger


@CeleryApp().app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_slack_events_task(self, payload: Dict[str, Any]):
    """
    Celery task to process Slack Events API callbacks.
    
    This is a thin driving adapter - receives Celery message and delegates
    to application layer (SlackEventService).
    
    Args:
        payload: Full Slack event payload from Events API
    """
    event_id = payload.get("event_id", "unknown")
    event = payload.get("event", {})
    event_type = event.get("type", "unknown")
    
    try:
        logger.info(f"Processing Slack event {event_id} ({event_type})")
        
        # Delegate to application layer (uses pre-registered handlers)
        service = slack_event_service()
        service.dispatch(payload)
        
        logger.info(f"Successfully processed Slack event {event_id}")
        
    except Exception as e:
        logger.error(f"Error processing Slack event {event_id}: {e}", exc_info=True)
        raise self.retry(exc=e)
