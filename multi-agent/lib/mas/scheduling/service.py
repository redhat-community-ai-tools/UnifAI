"""
Workflow schedule service -- application layer orchestrating schedule CRUD and lifecycle.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mas.blueprints.exceptions import BlueprintNotFoundError
from mas.blueprints.service import BlueprintService
from mas.core.identity import Identity
from mas.scheduling.models import (
    PromptSource,
    RunOutcome,
    RunStats,
    ScheduleDefinition,
    ScheduleStatus,
    WorkflowSchedule,
)
from mas.scheduling.ports import (
    BatchDescribeResult,
    ScheduleDescribeError,
    ScheduleEngine,
    ScheduleEngineError,
    ScheduleInfo,
    ScheduleNotFoundError as EngineScheduleNotFoundError,
)
from mas.scheduling.repository import WorkflowScheduleRepository
from mas.session.domain.models import ScheduleRunSummary
from mas.session.service import SessionService

logger = logging.getLogger(__name__)

MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT = 10


class ScheduleNotFoundError(Exception):
    """Raised when a workflow schedule is not found."""
    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Workflow schedule not found: {schedule_id}")


class ScheduleLimitExceededError(Exception):
    def __init__(self, blueprint_id: str, limit: int) -> None:
        self.blueprint_id = blueprint_id
        self.limit = limit
        super().__init__(
            f"Blueprint {blueprint_id} already has {limit} active schedules"
        )


class SchedulePermissionError(Exception):
    def __init__(self, resource_id: str, identity: Identity) -> None:
        self.resource_id = resource_id
        self.identity = identity
        super().__init__(
            f"Identity {identity.id} does not have permission on resource {resource_id}"
        )


class WorkflowScheduleService:
    def __init__(
        self,
        schedule_repo: WorkflowScheduleRepository,
        schedule_engine: ScheduleEngine,
        blueprint_service: BlueprintService,
        session_service: Optional[SessionService] = None,
    ) -> None:
        self._repo = schedule_repo
        self._schedule_engine = schedule_engine
        self._blueprint_service = blueprint_service
        self._session_service = session_service

    def create(
        self,
        *,
        identity: Identity,
        blueprint_id: str,
        inputs: Dict[str, Any],
        source: str = "manual",
        schedule: Dict[str, Any],
        credential_user_id: str = "",
    ) -> WorkflowSchedule:
        try:
            bp_doc = self._blueprint_service.get_blueprint_draft_doc(blueprint_id)
        except KeyError:
            raise BlueprintNotFoundError(blueprint_id)
        if not bp_doc.identity.owns(identity):
            raise SchedulePermissionError(blueprint_id, identity)

        active_count = self._repo.count_active_by_blueprint(blueprint_id)
        if active_count >= MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT:
            raise ScheduleLimitExceededError(blueprint_id, MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT)

        prompt_source = PromptSource(source)
        schedule_def = ScheduleDefinition(**schedule)

        wf_schedule = WorkflowSchedule(
            blueprint_id=blueprint_id,
            identity=identity,
            inputs=inputs,
            source=prompt_source,
            schedule=schedule_def,
            credential_user_id=credential_user_id,
        )
        self._repo.save(wf_schedule)

        try:
            handle = self._schedule_engine.create_schedule(wf_schedule)
        except ScheduleEngineError:
            self._repo.delete(wf_schedule.id)
            raise
        wf_schedule = wf_schedule.model_copy(update={"engine_handle": handle})
        if not self._repo.update(wf_schedule):
            try:
                self._schedule_engine.delete(handle)
            except EngineScheduleNotFoundError:
                logger.info(
                    "Engine schedule %s already absent during cleanup for schedule %s; no deletion needed",
                    handle, wf_schedule.id,
                )
            except ScheduleEngineError:
                logger.exception(
                    "Leaked engine schedule %s after repo update failure for schedule %s",
                    handle, wf_schedule.id,
                )
            raise ScheduleNotFoundError(wf_schedule.id)

        return wf_schedule

    def update(
        self,
        schedule_id: str,
        *,
        identity: Identity,
        inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[Dict[str, Any]] = None,
    ) -> WorkflowSchedule:
        wf_schedule = self._load_and_verify(schedule_id, identity)

        updates: Dict[str, Any] = {}
        if inputs is not None:
            updates["inputs"] = {**wf_schedule.inputs, **inputs}

        schedule_changed = False
        if schedule is not None:
            new_schedule = self._merge_schedule_definition(wf_schedule.schedule, schedule)
            if "remaining_actions" in schedule:
                self._validate_remaining_actions_against_runs(
                    new_schedule.remaining_actions,
                    wf_schedule,
                )
            if new_schedule != wf_schedule.schedule:
                updates["schedule"] = new_schedule
                schedule_changed = True

        if schedule_changed:
            new_sched: ScheduleDefinition = updates["schedule"]
            was_completed = wf_schedule.schedule_status == ScheduleStatus.COMPLETED

            if was_completed:
                # Reactivate: restart run tracking from zero.
                if self._is_schedule_already_exhausted(new_sched, 0):
                    updates["schedule_status"] = ScheduleStatus.COMPLETED
                    updates["completed_at"] = datetime.now(timezone.utc)
                else:
                    updates["schedule_status"] = ScheduleStatus.ACTIVE
                    updates["completed_at"] = None
                    updates["run_stats"] = RunStats()
            else:
                # Active/paused: keep run_stats and status unless newly exhausted.
                if self._is_schedule_already_exhausted(
                    new_sched, wf_schedule.run_stats.total_runs,
                ):
                    updates["schedule_status"] = ScheduleStatus.COMPLETED
                    updates["completed_at"] = datetime.now(timezone.utc)

        if updates:
            wf_schedule = wf_schedule.model_copy(update=updates)
            wf_schedule = self._sync_engine_after_update(wf_schedule)

        self._persist_after_external_mutation(wf_schedule)
        return wf_schedule

    def _sync_engine_after_update(self, wf_schedule: WorkflowSchedule) -> WorkflowSchedule:
        """Push definition to the engine; recreate if the engine schedule was deleted."""
        if wf_schedule.engine_handle:
            try:
                self._schedule_engine.update_schedule(
                    wf_schedule.engine_handle, wf_schedule,
                )
                return wf_schedule
            except EngineScheduleNotFoundError:
                logger.info(
                    "Engine schedule %s missing for %s — recreating",
                    wf_schedule.engine_handle, wf_schedule.id,
                )
        handle = self._schedule_engine.create_schedule(wf_schedule)
        return wf_schedule.model_copy(update={"engine_handle": handle})

    @staticmethod
    def _merge_schedule_definition(
        existing: ScheduleDefinition, patch: Dict[str, Any],
    ) -> ScheduleDefinition:
        """Merge a partial schedule patch onto the existing definition.

        Omitted keys (notably ``start_at`` / ``remaining_actions``) keep their
        current values so recurrence-only edits do not rewrite start time or
        the configured ends-after limit.
        """
        data = existing.model_dump(mode="python")

        if patch.get("interval") is not None:
            data["interval"] = patch["interval"]
            data["cron_expression"] = None
        if patch.get("cron_expression") is not None:
            data["cron_expression"] = patch["cron_expression"]
            data["interval"] = None

        for key in ("overlap_policy", "timezone", "enabled", "start_at", "end_at"):
            if key in patch:
                data[key] = patch[key]

        if "remaining_actions" in patch:
            data["remaining_actions"] = patch["remaining_actions"]

        return ScheduleDefinition(**data)

    @staticmethod
    def _validate_remaining_actions_against_runs(
        remaining_actions: Optional[int],
        wf_schedule: WorkflowSchedule,
    ) -> None:
        """Reject ends-after values below runs already completed.

        ``remaining_actions == total_runs`` is valid — it means the schedule is
        exhausted and should transition to COMPLETED. Only values strictly less
        than ``total_runs`` are rejected (e.g. ran 6 times, set ends-after to 5).

        Skipped when reactivating a COMPLETED schedule (run tracking resets to 0).
        """
        if remaining_actions is None:
            return
        if wf_schedule.schedule_status == ScheduleStatus.COMPLETED:
            return
        total_runs = wf_schedule.run_stats.total_runs
        if remaining_actions < total_runs:
            raise ValueError(
                f"Ends after cannot be less than runs already completed "
                f"({total_runs} run(s) so far; got ends-after {remaining_actions})"
            )

    @staticmethod
    def _is_schedule_already_exhausted(
        schedule: ScheduleDefinition, total_runs: int,
    ) -> bool:
        if (
            schedule.remaining_actions is not None
            and total_runs >= schedule.remaining_actions
        ):
            return True
        if schedule.end_at is not None and schedule.end_at <= datetime.now(timezone.utc):
            return True
        return False

    def pause(self, schedule_id: str, *, identity: Identity) -> WorkflowSchedule:
        wf_schedule = self._load_and_verify(schedule_id, identity)

        if wf_schedule.engine_handle:
            try:
                self._schedule_engine.pause(wf_schedule.engine_handle)
            except EngineScheduleNotFoundError:
                logger.warning(
                    "Engine schedule %s already removed for schedule %s during pause",
                    wf_schedule.engine_handle,
                    schedule_id,
                )

        wf_schedule = wf_schedule.model_copy(update={"schedule_status": ScheduleStatus.PAUSED})
        self._persist_after_external_mutation(wf_schedule)
        return wf_schedule

    def resume(self, schedule_id: str, *, identity: Identity) -> WorkflowSchedule:
        wf_schedule = self._load_and_verify(schedule_id, identity)

        if wf_schedule.engine_handle:
            try:
                self._schedule_engine.resume(wf_schedule.engine_handle)
            except EngineScheduleNotFoundError:
                logger.warning(
                    "Engine schedule %s already removed for schedule %s during resume",
                    wf_schedule.engine_handle,
                    schedule_id,
                )

        wf_schedule = wf_schedule.model_copy(update={"schedule_status": ScheduleStatus.ACTIVE})
        self._persist_after_external_mutation(wf_schedule)
        return wf_schedule

    def trigger(self, schedule_id: str, *, identity: Identity) -> WorkflowSchedule:
        """Trigger an immediate one-off execution of the schedule."""
        wf_schedule = self._load_and_verify(schedule_id, identity)

        if not wf_schedule.engine_handle:
            raise ValueError(
                f"Schedule {schedule_id} has no active engine handle to trigger"
            )

        try:
            self._schedule_engine.trigger_now(wf_schedule.engine_handle)
        except EngineScheduleNotFoundError as exc:
            raise ScheduleNotFoundError(schedule_id) from exc
        return wf_schedule

    def delete(self, schedule_id: str, *, identity: Identity) -> None:
        wf_schedule = self._load_and_verify(schedule_id, identity)

        if wf_schedule.engine_handle:
            try:
                self._schedule_engine.delete(wf_schedule.engine_handle)
            except EngineScheduleNotFoundError:
                logger.warning(
                    "Engine schedule %s already removed for schedule %s",
                    wf_schedule.engine_handle,
                    schedule_id,
                )

        self._repo.delete(schedule_id)

    def list(self, *, identity: Identity) -> List[WorkflowSchedule]:
        return self._repo.list_by_identity(identity)

    def list_enriched(
        self,
        *,
        identity: Identity,
        blueprint_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return schedule dicts enriched with ``blueprint_name``."""
        if blueprint_id:
            schedules = [
                s for s in self._repo.find_by_blueprint(blueprint_id)
                if s.identity.owns(identity)
            ]
        else:
            schedules = self._repo.list_by_identity(identity)

        schedules = self._reconcile_batch(schedules)

        name_cache: Dict[str, str] = {}
        result: List[Dict[str, Any]] = []
        for s in schedules:
            d = s.model_dump(mode="json", exclude={"credential_user_id"})
            bid = s.blueprint_id
            if bid not in name_cache:
                name_cache[bid] = self._get_blueprint_name(bid)
            d["blueprint_name"] = name_cache[bid]
            result.append(d)
        return result

    def _get_blueprint_name(self, blueprint_id: str) -> str:
        try:
            doc = self._blueprint_service.get_blueprint_draft_doc(blueprint_id)
            return doc.spec_dict.get("name", blueprint_id)
        except (KeyError, BlueprintNotFoundError):
            return blueprint_id

    def record_run(
        self,
        schedule_id: str,
        session_id: str,
        status: RunOutcome,
        started_at: datetime,
    ) -> None:
        """Record a completed run in the schedule's embedded run_stats."""
        self._repo.record_run(schedule_id, session_id, status, started_at)

    def record_outcome(
        self,
        schedule_id: str,
        session_id: str,
        outcome: RunOutcome,
        started_at: datetime,
    ) -> None:
        """Record a run outcome and mark the schedule completed if exhausted."""
        self.record_run(schedule_id, session_id, outcome, started_at)
        self.mark_completed(schedule_id)

    def get(self, schedule_id: str, *, identity: Identity) -> WorkflowSchedule:
        wf_schedule = self._load_and_verify(schedule_id, identity)
        return self._reconcile_if_needed(wf_schedule)

    def get_runs(
        self, schedule_id: str, *, identity: Identity, limit: int = 20,
    ) -> List[ScheduleRunSummary]:
        """Return run history for a schedule, with ownership verification."""
        self._load_and_verify(schedule_id, identity)
        if not self._session_service:
            return []
        return self._session_service.get_runs_by_schedule(schedule_id, limit=limit)

    def mark_completed(self, schedule_id: str) -> None:
        """Transition a finite schedule to COMPLETED if exhausted."""
        try:
            wf_schedule = self._repo.load(schedule_id)
        except KeyError:
            logger.warning("mark_completed: schedule %s not found", schedule_id)
            return

        if wf_schedule.schedule_status != ScheduleStatus.ACTIVE:
            return

        if not self._is_schedule_already_exhausted(
            wf_schedule.schedule, wf_schedule.run_stats.total_runs,
        ):
            return

        wf_schedule = wf_schedule.model_copy(update={
            "schedule_status": ScheduleStatus.COMPLETED,
            "completed_at": datetime.now(timezone.utc),
        })
        self._persist_best_effort(wf_schedule)

    def _reconcile_batch(self, schedules: List[WorkflowSchedule]) -> List[WorkflowSchedule]:
        needs_reconcile: Dict[str, int] = {}
        for idx, s in enumerate(schedules):
            if (
                s.schedule_status == ScheduleStatus.ACTIVE
                and s.engine_handle
                and (s.schedule.remaining_actions is not None or s.schedule.end_at is not None)
            ):
                needs_reconcile[s.engine_handle] = idx

        if not needs_reconcile:
            return schedules

        batch_result = self._schedule_engine.describe_batch(list(needs_reconcile.keys()))

        result = list(schedules)
        for sched_id, idx in needs_reconcile.items():
            if sched_id in batch_result.errored:
                continue

            info = batch_result.found.get(sched_id)
            if info is None or not info.running:
                result[idx] = self._mark_exhausted(result[idx])

        return result

    def _reconcile_if_needed(self, wf_schedule: WorkflowSchedule) -> WorkflowSchedule:
        if wf_schedule.schedule_status != ScheduleStatus.ACTIVE:
            return wf_schedule
        if not wf_schedule.engine_handle:
            return wf_schedule

        is_finite = (
            wf_schedule.schedule.remaining_actions is not None
            or wf_schedule.schedule.end_at is not None
        )
        if not is_finite:
            return wf_schedule

        try:
            info = self._schedule_engine.describe(wf_schedule.engine_handle)
        except EngineScheduleNotFoundError:
            info = None
        except ScheduleDescribeError:
            logger.debug(
                "reconcile: describe failed for schedule %s, skipping", wf_schedule.id,
            )
            return wf_schedule

        if info is None or not info.running:
            return self._mark_exhausted(wf_schedule)

        return wf_schedule

    def _mark_exhausted(self, wf_schedule: WorkflowSchedule) -> WorkflowSchedule:
        """Transition a schedule to COMPLETED and persist best-effort."""
        logger.info(
            "reconcile: marking schedule %s COMPLETED — engine schedule exhausted",
            wf_schedule.id,
        )
        wf_schedule = wf_schedule.model_copy(update={
            "schedule_status": ScheduleStatus.COMPLETED,
            "completed_at": datetime.now(timezone.utc),
        })
        self._persist_best_effort(wf_schedule)
        return wf_schedule

    def _persist_after_external_mutation(self, wf_schedule: WorkflowSchedule) -> None:
        if not self._repo.update(wf_schedule):
            raise ScheduleNotFoundError(wf_schedule.id)

    def _persist_best_effort(self, wf_schedule: WorkflowSchedule) -> None:
        if not self._repo.update(wf_schedule):
            logger.warning(
                "repo.update returned False for schedule %s — document may have been deleted concurrently",
                wf_schedule.id,
            )

    def _load_and_verify(self, schedule_id: str, identity: Identity) -> WorkflowSchedule:
        try:
            wf_schedule = self._repo.load(schedule_id)
        except KeyError:
            raise ScheduleNotFoundError(schedule_id)

        if not wf_schedule.identity.owns(identity):
            raise SchedulePermissionError(schedule_id, identity)

        return wf_schedule
