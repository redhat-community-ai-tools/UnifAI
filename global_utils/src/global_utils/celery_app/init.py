"""
Module for importing non-configured flask extensions
"""
from celery import Celery
from global_utils.utils.util import get_mongo_url, get_rabbitmq_url
import logging


class CeleryApp:
    """
    Singleton class for initializing and configuring Celery.
    """
    _instance = None

    def __new__(cls,  broker_user_name=None, broker_password=None, task_modules=[]):
        if cls._instance is None:
            cls._instance = super(CeleryApp, cls).__new__(cls)
            cls._instance._initialize_celery(broker_user_name, broker_password, task_modules)
        return cls._instance

    def _initialize_celery(self, broker_user_name, broker_password, task_modules):
        """Initialize the Celery instance."""        
        broker_url = get_rabbitmq_url(broker_user_name, broker_password)

        self.celery_app = Celery(
            'celery_util',
            broker=broker_url,
            backend=get_mongo_url(),
            include=task_modules  # Accept list of task module paths
        )

        self.celery_app.conf.update(
            broker_transport_options={
                'heartbeat': 3600,              # overrides broker_heartbeat at transport level
                'socket_keepalive': True,       # keep TCP socket alive
            },
            task_acks_late=False,
            task_reject_on_worker_lost=False,
            worker_hijack_root_logger=False,
            worker_cancel_long_running_tasks_on_connection_loss=True,
            worker_log_format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            worker_task_log_format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        )

        # Use process root handlers from configure_logging (stdout / optional file).
        celery_logger = logging.getLogger('celery')
        celery_logger.handlers.clear()
        celery_logger.setLevel(logging.getLogger().level)
        celery_logger.propagate = True

    @property
    def app(self):
        """Get the singleton Celery instance."""
        return self.celery_app
    
# ✅ Example Usage in Another Project
# from global_utils.celery_app import CeleryApp
# from global_utils.utils.logging_config import logger

# celery_instance = CeleryApp(
#     broker_user_name="guest",
#     broker_password="guest",
#     task_modules=["project_X.tasks.{file_name}"]
# )

# app = celery_instance.app
