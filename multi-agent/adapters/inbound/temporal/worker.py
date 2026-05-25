"""
Temporal worker — inbound adapter.

Receives a fully-wired AppContainer from its entry point
(bootstrap/cli.py) and uses it to build activity instances.
This adapter never creates the container itself.

Multiple workers can run concurrently for horizontal scaling.

Usage via CLI::

    mas temporal-worker --threads 20
    mas temporal-worker --threads 20 --workflow-pollers 10
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from temporalio.worker import Worker, UnsandboxedWorkflowRunner

from config.app_config import AppConfig
from mas.engine.distributed.node_executor import NodeExecutor
from mas.session.execution.lifecycle_handler import BackgroundLifecycleHandler
from mas.session.execution.lifecycle import SessionLifecycle
from temporal.client import get_temporal_client
from inbound.temporal.activities import GraphNodeActivities, SessionLifecycleActivities
from inbound.temporal.workflows import GraphTraversalWorkflow, SessionWorkflow


async def run_worker(
    container,
    *,
    threads: int = 10,
    max_workflow_tasks: Optional[int] = None,
    workflow_pollers: int = 5,
    activity_pollers: int = 5,
) -> None:
    cfg = AppConfig.get_instance()

    node_executor = NodeExecutor(
        session_factory=container.session_factory,
    )

    thread_pool = ThreadPoolExecutor(max_workers=threads)

    graph_activities = GraphNodeActivities(
        node_executor=node_executor,
        channel_factory=container.channel_factory,
    )

    lifecycle = SessionLifecycle(repository=container.session_repo)
    lifecycle_handler = BackgroundLifecycleHandler(
        session_manager=container.session_manager,
        lifecycle=lifecycle,
        channel_factory=container.channel_factory,
    )
    lifecycle_activities = SessionLifecycleActivities(
        handler=lifecycle_handler,
    )

    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=cfg.temporal_task_queue,
        workflows=[GraphTraversalWorkflow, SessionWorkflow],
        activities=[
            graph_activities.execute_node,
            graph_activities.evaluate_condition,
            lifecycle_activities.begin_session,
            lifecycle_activities.complete_session,
            lifecycle_activities.fail_session,
            lifecycle_activities.cancel_session,
        ],
        activity_executor=thread_pool,
        max_concurrent_activities=threads,
        max_concurrent_workflow_tasks=max_workflow_tasks,
        max_concurrent_workflow_task_polls=workflow_pollers,
        max_concurrent_activity_task_polls=activity_pollers,
        workflow_runner=UnsandboxedWorkflowRunner(),
    )

    print(
        f"Worker started | task_queue={cfg.temporal_task_queue} "
        f"| threads={threads} | workflow_pollers={workflow_pollers} "
        f"| activity_pollers={activity_pollers}"
    )
    await worker.run()
