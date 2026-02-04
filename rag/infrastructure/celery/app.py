"""Celery app initialization for RAG workers."""
from config.app_config import AppConfig
from global_utils.celery_app import CeleryApp

config = AppConfig.get_instance()

celery = CeleryApp(
    broker_user_name=config.broker_user_name,
    broker_password=config.broker_password,
    task_modules=[
        "infrastructure.celery.workers.pipeline_tasks",
        "infrastructure.celery.workers.slack_event_tasks",
    ]
).app

# To start celery worker from rag/:
# celery -A infrastructure.celery.app worker -c 1 --loglevel=info -Q slack_queue -n slack_worker
# celery -A infrastructure.celery.app worker -c 1 --loglevel=info -Q document_queue -n document_worker

