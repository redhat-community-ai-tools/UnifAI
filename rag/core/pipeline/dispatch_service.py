"""Pipeline dispatch service - orchestrates registration and task dispatch."""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from core.registration.service import RegistrationService
from core.pipeline.domain.dispatcher import PipelineTaskDispatcher, TaskResult
from shared.logger import logger


@dataclass
class PipelineStartResult:
    """Result of starting a pipeline workflow."""
    registration_completed: bool
    registered_count: int
    tasks_dispatched: int
    registration_response: Dict[str, Any]
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "registration_completed": self.registration_completed,
            "registration": self.registration_response,
            "pipeline_execution": {
                "status": "pipeline_workflow_started" if self.tasks_dispatched > 0 else "no_registered_sources",
                "message": f"Pipeline started for {self.registered_count} sources" if self.tasks_dispatched > 0 
                          else "No sources registered; skipping pipeline execution",
                "pipeline_worker_tasks_submitted": self.tasks_dispatched,
                "source_count": self.registered_count,
                "tasks": self.task_results,
            },
        }


class PipelineDispatchService:
    """
    Application service that orchestrates source registration and pipeline dispatch.
    
    This is the main entry point for the /pipelines/embed endpoint.
    It coordinates:
    1. Source registration (validation, record creation)
    2. Task dispatch to async workers (via port, not directly to Celery)
    
    The service depends on the PipelineTaskDispatcher PORT, not on Celery directly,
    following Hexagonal Architecture principles.
    """

    def __init__(
        self,
        registration_svc: RegistrationService,
        task_dispatcher: PipelineTaskDispatcher,
    ):
        """
        Initialize with injected dependencies.
        
        Args:
            registration_svc: Service for registering sources
            task_dispatcher: Port for dispatching async tasks (injected adapter)
        """
        self._registration = registration_svc
        self._dispatcher = task_dispatcher

    def start_pipeline(
        self,
        data: List[Dict[str, Any]],
        source_type: str,
        upload_by: str,
        skip_validation: bool = False,
    ) -> PipelineStartResult:
        """
        Start the pipeline workflow for provided data sources.
        
        Performs registration synchronously, then dispatches pipeline
        execution tasks to async workers.
        
        Args:
            data: List of data sources to register and process
            source_type: Type of data source (DOCUMENT, SLACK, etc.)
            upload_by: Username of the current user
            skip_validation: If True, skip file validation during registration.
                            Should only be True when files have been pre-validated
                            via the /docs/validate endpoint (UI flow).
        
        Returns:
            PipelineStartResult with registration and dispatch details
        """
        logger.info(f"Starting pipeline for {len(data)} {source_type} sources by {upload_by}")

        # 1. Register sources
        reg_response = self._registration.register_sources(
            data_list=data,
            source_type=source_type.upper(),
            upload_by=upload_by,
            skip_validation=skip_validation,
        )

        registered_sources = reg_response.get("registered_sources", [])

        # 2. Dispatch pipeline tasks
        task_results: List[TaskResult] = []
        if registered_sources:
            try:
                task_results = self._dispatcher.dispatch_batch(
                    source_type=source_type.upper(),
                    sources=registered_sources,
                )
                logger.info(f"Dispatched {len(task_results)} pipeline tasks")
            except Exception as e:
                logger.error(f"Failed to dispatch pipeline tasks: {e}")
                raise

        return PipelineStartResult(
            registration_completed=True,
            registered_count=len(registered_sources),
            tasks_dispatched=len(task_results),
            registration_response=reg_response,
            task_results=[t.to_dict() for t in task_results],
        )
