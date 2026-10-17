"""Celery app initialization for RAG workers."""
from config.app_config import AppConfig
from celery.signals import worker_init, worker_process_init

from global_utils.celery_app import CeleryApp
from global_utils.telemetry import init_telemetry
from global_utils.utils.logging_config import configure_logging

configure_logging("rag-celery")
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


@worker_init.connect
@worker_process_init.connect
def _init_worker_telemetry(**_kwargs):
    """Start OpenTelemetry in the process that executes tasks.

    Inert unless OTEL_EXPORTER_OTLP_ENDPOINT (or UNIFAI_OTEL_ENABLED) is set.
    Hooked on worker start rather than on import, because the API process
    imports this module too (to publish tasks) and initialises telemetry
    under its own service name.  worker_process_init covers prefork children;
    init_telemetry() is idempotent per process.
    """
    init_telemetry("rag-celery", celery=True)
