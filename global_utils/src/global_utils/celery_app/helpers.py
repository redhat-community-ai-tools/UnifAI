import sys
import time
from kombu import Connection
from celery import worker
from global_utils.celery_app import CeleryApp
from global_utils.utils.util import get_rabbitmq_url
from global_utils.utils.logging_config import logger


def send_task(task_name, celery_queue, **kwargs):
    from global_utils.flask.correlation import celery_correlation_headers
    headers = celery_correlation_headers()
    CeleryApp().app.send_task(
        task_name,
        kwargs=kwargs,
        queue=celery_queue,
        headers=headers or None,
    )


def is_celery_queue_empty(queue_name: str) -> bool:
    """
    Checks if a given Celery queue is empty by inspecting both reserved and scheduled tasks.

    Args:
        queue_name (str): Name of the queue to check.

    Returns:
        bool: True if the queue is empty, False otherwise.
    """
    inspect = CeleryApp().app.control.inspect()
    # Check reserved tasks
    reserved_tasks = inspect.reserved()

    if reserved_tasks:
        for worker, tasks in reserved_tasks.items():
            for task in tasks:
                if task.get('delivery_info', {}).get('routing_key') == queue_name:
                    logger.debug(f"Queue '{queue_name}' is not empty. Found reserved task: {task['name']}")
                    return False
    return True


def get_queue_length_rabbitmq(queue_name):
    with Connection(get_rabbitmq_url()) as conn:
        queue = conn.SimpleQueue(queue_name)
        return queue.qsize()


def is_queue_full(queue_name, queue_target_size, max_retries=3, retry_delay=5) -> bool:
    """
    Check if the RabbitMQ queue is full with retry mechanism.

    Args:
        queue_name (str): The name of the RabbitMQ queue.
        queue_target_size (int): The maximum allowed size of the queue.
        max_retries (int): The maximum number of retries before failing.
        retry_delay (int): Delay in seconds between retries.

    Returns:
        bool: True if the queue is full, False otherwise.

    Raises:
        Exception: If retries are exhausted and the operation fails.
    """
    retries = 0

    while retries <= max_retries:
        try:
            queue_length = get_queue_length_rabbitmq(queue_name)
            logger.debug(f"queue_length: {queue_length}  queue_target_size: {queue_target_size} ")
            return queue_length >= queue_target_size
        except Exception as e:
            retries += 1
            logger.debug(f"[Orchestrator] Error checking queue length (attempt {retries}/{max_retries}): {e}")
            if retries > max_retries:
                logger.debug("[Orchestrator] Max retries reached. Failing.")
                raise  # Re-raise the last exception
            time.sleep(retry_delay)


def start_celery_worker(queue_name, loglevel="info", prefetch_count=1, concurrency=1, worker_name=None):
    """
    Start a Celery worker programmatically.

    Args:
        queue_name (str): The name of the queue to listen on.
        loglevel (str): Logging level for the Celery worker.
        prefetch_count (int): The number of tasks a worker can prefetch. Default is 1.
        concurrency (int): The number of worker processes/threads. Default is 1.
        worker_name (str): Optional name for the worker instance.
    """
    # Create a Celery app instance
    app = CeleryApp().app

    # Set concurrency and prefetch count in the Celery configuration
    app.conf.worker_prefetch_multiplier = prefetch_count
    app.conf.worker_concurrency = concurrency

    # Start the worker
    try:
        worker_hostname = worker_name or f"worker@{queue_name}"  # Default worker name
        logger.info(f"Starting Celery worker listening on queue: {queue_name}")
        logger.info(f"Prefetch count: {prefetch_count}, Concurrency: {concurrency}")
        logger.info(f"Worker name: {worker_hostname}")

        # Create and start the worker instance
        worker_instance = worker.WorkController(
            app=app, loglevel=loglevel, hostname=worker_hostname, queues=[queue_name]
        )
        worker_instance.start()
    except KeyboardInterrupt:
        logger.info("Worker stopped manually.")
        sys.exit(0)
