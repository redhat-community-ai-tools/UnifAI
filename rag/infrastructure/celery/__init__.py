"""Celery infrastructure adapters.

Structure:
- dispatchers/ - Driven adapters (app → Celery): send tasks to queue
- workers/     - Driving adapters (Celery → app): receive tasks from queue

Dispatchers:
    CeleryPipelineDispatcher - Dispatch pipeline execution tasks
    CelerySlackEventDispatcher - Dispatch Slack event processing tasks

Workers:
    execute_pipeline_task - Celery task for pipeline execution
"""
from infrastructure.celery.pipeline_dispatcher import CeleryPipelineDispatcher
from infrastructure.celery.slack_event_dispatcher import CelerySlackEventDispatcher

__all__ = [
    # Dispatchers (driven adapters)
    "CeleryPipelineDispatcher",
    "CelerySlackEventDispatcher",
]
