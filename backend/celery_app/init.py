from config.app_config import AppConfig
from global_utils.celery_app import CeleryApp

config = AppConfig.get_instance()
celery = CeleryApp(
    broker_user_name=config.broker_user_name, 
    broker_password=config.broker_password,
    task_modules=[
        "celery_app.tasks.pipeline_tasks",
        "celery_app.tasks.slack_event_subscription_tasks"
    ]
).app

# TODO: In order to start celery worker, below line should be triggered from backend/
# For separate workers by source type:
# celery -A celery_app.init worker -c 1 --loglevel=info -Q slack_queue -n slack_worker  
# celery -A celery_app.init worker -c 1 --loglevel=info -Q document_queue -n document_worker