"""Slack event dispatch service - handles Slack Events API webhooks."""
from dataclasses import dataclass
from typing import Dict, Any, Optional

from core.data_sources.types.slack.domain.event.dispatcher import SlackEventDispatcher, SlackEventTaskResult
from shared.logger import logger


@dataclass
class SlackEventResponse:
    """Response for Slack event handling."""
    success: bool
    event_type: str
    message: str
    task_result: Optional[SlackEventTaskResult] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "event_type": self.event_type,
            "message": self.message,
        }
        if self.task_result:
            result["task"] = self.task_result.to_dict()
        return result


class SlackEventDispatchService:
    """
    Application service for handling Slack Events API webhooks.
    
    Responsibilities:
    - Handle URL verification (Slack health check)
    - Dispatch event_callback payloads to async workers
    
    The service depends on the SlackEventDispatcher PORT, not on Celery directly,
    following Hexagonal Architecture principles.
    """

    def __init__(self, dispatcher: SlackEventDispatcher):
        """
        Initialize with injected dispatcher.
        
        Args:
            dispatcher: Port for dispatching async tasks (injected adapter)
        """
        self._dispatcher = dispatcher

    def handle_webhook(self, payload: Dict[str, Any]) -> SlackEventResponse:
        """
        Handle incoming Slack Events API webhook.
        
        Handles two payload types:
        1. url_verification - Slack health check, returns challenge
        2. event_callback - Actual event, dispatched to async worker
        
        Args:
            payload: Raw payload from Slack Events API
            
        Returns:
            SlackEventResponse with handling result
        """
        payload_type = payload.get("type", "unknown")

        # URL verification (Slack health check)
        if payload_type == "url_verification":
            challenge = payload.get("challenge", "")
            logger.info("Slack URL verification challenge received")
            return SlackEventResponse(
                success=True,
                event_type="url_verification",
                message=challenge,  # The challenge is returned in message for endpoint to use
            )

        # Event callback - dispatch to worker
        if payload_type == "event_callback":
            event_id = payload.get("event_id", "unknown")
            try:
                task_result = self._dispatcher.dispatch(payload)
                logger.info(f"Dispatched Slack event {event_id}")
                return SlackEventResponse(
                    success=True,
                    event_type="event_callback",
                    message="Event dispatched for processing",
                    task_result=task_result,
                )
            except Exception as e:
                logger.error(f"Failed to dispatch Slack event {event_id}: {e}")
                return SlackEventResponse(
                    success=False,
                    event_type="event_callback",
                    message=f"Failed to dispatch event: {e}",
                )

        # Unknown payload type
        logger.warning(f"Unknown Slack event type: {payload_type}")
        return SlackEventResponse(
            success=True,  # Still return 200 to Slack
            event_type=payload_type,
            message="Unknown event type, ignored",
        )
