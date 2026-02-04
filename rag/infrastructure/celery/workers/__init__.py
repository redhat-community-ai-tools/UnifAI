"""Celery workers (driving adapters) - receive tasks from queue and delegate to application."""
from infrastructure.celery.workers.pipeline_tasks import execute_pipeline_task
from infrastructure.celery.workers.slack_event_tasks import process_slack_events_task

__all__ = ["execute_pipeline_task", "process_slack_events_task"]

