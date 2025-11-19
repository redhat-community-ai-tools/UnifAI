"""
Celery tasks for Slack event subscriptions.
"""
from typing import Dict, Any
from global_utils.celery_app import CeleryApp
from shared.logger import logger
from services.slack_events.slack_events_service import SlackEventService
from services.slack_events.handlers.channel_created_handler import ChannelCreatedEventHandler


@CeleryApp().app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_slack_events_task(self, payload: Dict[str, Any]):
    """
    Celery task to process Slack Events API callbacks.
    
    Args:
        payload: Full Slack event payload
    """
    try:
        _event_service = SlackEventService()
        _event_service.register_class(ChannelCreatedEventHandler)
        _event_service.dispatch(payload)
    except Exception as e:
        logger.error(f"Error processing Slack event {payload.get('event_id')}: {e}", exc_info=True)
        raise self.retry(exc=e)


