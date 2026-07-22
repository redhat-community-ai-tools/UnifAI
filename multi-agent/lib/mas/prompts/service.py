"""
Prompt service -- application layer orchestrating prompt CRUD and schedule lifecycle.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mas.blueprints.exceptions import BlueprintNotFoundError
from mas.blueprints.service import BlueprintService
from mas.core.identity import Identity
from mas.prompts.models import (
    PromptSource,
    ScheduleDefinition,
    ScheduleStatus,
    ScheduledPrompt,
)
from mas.prompts.ports import ScheduleNotFoundError, SchedulePort
from mas.prompts.repository import ScheduledPromptRepository
from mas.session.service import SessionService

logger = logging.getLogger(__name__)

MAX_ACTIVE_PROMPTS_PER_BLUEPRINT = 10


class PromptNotFoundError(Exception):
    def __init__(self, prompt_id: str) -> None:
        self.prompt_id = prompt_id
        super().__init__(f"Scheduled prompt not found: {prompt_id}")


class PromptLimitExceededError(Exception):
    def __init__(self, blueprint_id: str, limit: int) -> None:
        self.blueprint_id = blueprint_id
        self.limit = limit
        super().__init__(
            f"Blueprint {blueprint_id} already has {limit} active scheduled prompts"
        )


class PromptPermissionError(Exception):
    def __init__(self, prompt_id: str, identity: Identity) -> None:
        self.prompt_id = prompt_id
        self.identity = identity
        super().__init__(
            f"Identity {identity.id} does not own prompt {prompt_id}"
        )


class PromptService:
    def __init__(
        self,
        prompt_repo: ScheduledPromptRepository,
        schedule_port: Optional[SchedulePort],
        blueprint_service: BlueprintService,
        session_service: Optional[SessionService] = None,
    ) -> None:
        self._repo = prompt_repo
        self._schedule_port = schedule_port
        self._blueprint_service = blueprint_service
        self._session_service = session_service

    def create(
        self,
        *,
        identity: Identity,
        blueprint_id: str,
        text: str,
        inputs: Optional[Dict[str, Any]] = None,
        source: str = "manual",
        schedule: Dict[str, Any],
    ) -> ScheduledPrompt:
        try:
            bp_doc = self._blueprint_service.get_blueprint_draft_doc(blueprint_id)
        except KeyError:
            raise BlueprintNotFoundError(blueprint_id)
        if not bp_doc.identity.owns(identity):
            raise PromptPermissionError(blueprint_id, identity)

        active_count = self._repo.count_active_by_blueprint(blueprint_id)
        if active_count >= MAX_ACTIVE_PROMPTS_PER_BLUEPRINT:
            raise PromptLimitExceededError(blueprint_id, MAX_ACTIVE_PROMPTS_PER_BLUEPRINT)

        prompt_source = PromptSource(source)
        schedule_def = ScheduleDefinition(**schedule)

        prompt = ScheduledPrompt(
            blueprint_id=blueprint_id,
            identity=identity,
            text=text,
            inputs=inputs or {},
            source=prompt_source,
            schedule=schedule_def,
        )
        self._repo.save(prompt)

        if self._schedule_port:
            temporal_id = self._schedule_port.create_schedule(prompt)
            prompt = prompt.model_copy(update={"temporal_schedule_id": temporal_id})
            self._update_or_warn(prompt)

        return prompt

    def update(
        self,
        prompt_id: str,
        *,
        identity: Identity,
        text: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[Dict[str, Any]] = None,
    ) -> ScheduledPrompt:
        prompt = self._load_and_verify(prompt_id, identity)

        updates: Dict[str, Any] = {}
        if text is not None:
            updates["text"] = text
        if inputs is not None:
            updates["inputs"] = inputs

        schedule_changed = False
        if schedule is not None:
            new_schedule = ScheduleDefinition(**schedule)
            if new_schedule != prompt.schedule:
                updates["schedule"] = new_schedule
                schedule_changed = True

        if schedule_changed:
            new_sched: ScheduleDefinition = updates["schedule"]
            if self._is_schedule_already_exhausted(new_sched, prompt.run_stats.total_runs):
                updates["schedule_status"] = ScheduleStatus.COMPLETED
                updates["completed_at"] = datetime.now(timezone.utc)
            else:
                updates["schedule_status"] = ScheduleStatus.ACTIVE
                updates["completed_at"] = None

        if updates:
            prompt = prompt.model_copy(update=updates)

        if schedule_changed and self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.update_schedule(prompt.temporal_schedule_id, prompt)

        self._update_or_warn(prompt)
        return prompt

    @staticmethod
    def _is_schedule_already_exhausted(
        schedule: ScheduleDefinition, total_runs: int,
    ) -> bool:
        """Return True if the schedule has no future actions left."""
        if (
            schedule.remaining_actions is not None
            and total_runs >= schedule.remaining_actions
        ):
            return True
        if schedule.end_at is not None and schedule.end_at <= datetime.now(timezone.utc):
            return True
        return False

    def pause(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.pause(prompt.temporal_schedule_id)

        prompt = prompt.model_copy(update={"schedule_status": ScheduleStatus.PAUSED})
        self._update_or_warn(prompt)
        return prompt

    def resume(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.resume(prompt.temporal_schedule_id)

        prompt = prompt.model_copy(update={"schedule_status": ScheduleStatus.ACTIVE})
        self._update_or_warn(prompt)
        return prompt

    def trigger(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        """Trigger an immediate one-off execution of the schedule."""
        prompt = self._load_and_verify(prompt_id, identity)

        if not self._schedule_port or not prompt.temporal_schedule_id:
            raise ValueError(
                f"Prompt {prompt_id} has no active Temporal schedule to trigger"
            )

        self._schedule_port.trigger_now(prompt.temporal_schedule_id)
        return prompt

    def delete(self, prompt_id: str, *, identity: Identity) -> None:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            try:
                self._schedule_port.delete(prompt.temporal_schedule_id)
            except ScheduleNotFoundError:
                logger.warning(
                    "Temporal schedule %s already removed for prompt %s",
                    prompt.temporal_schedule_id,
                    prompt_id,
                )

        self._repo.delete(prompt_id)

    def list(self, *, identity: Identity) -> List[ScheduledPrompt]:
        return self._repo.list_by_identity(identity)

    def list_enriched(
        self,
        *,
        identity: Identity,
        blueprint_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return prompt dicts enriched with ``blueprint_name``.

        Accepts an optional *blueprint_id* filter.  Results are always
        scoped to the caller's identity.
        """
        if blueprint_id:
            prompts = [
                p for p in self._repo.find_by_blueprint(blueprint_id)
                if p.identity.owns(identity)
            ]
        else:
            prompts = self._repo.list_by_identity(identity)

        name_cache: Dict[str, str] = {}
        result: List[Dict[str, Any]] = []
        for p in prompts:
            d = p.model_dump(mode="json")
            bid = p.blueprint_id
            if bid not in name_cache:
                name_cache[bid] = self._get_blueprint_name(bid)
            d["blueprint_name"] = name_cache[bid]
            result.append(d)
        return result

    def _get_blueprint_name(self, blueprint_id: str) -> str:
        """Resolve blueprint display name, falling back to the raw ID."""
        try:
            doc = self._blueprint_service.get_blueprint_draft_doc(blueprint_id)
            return doc.spec_dict.get("name", blueprint_id)
        except (KeyError, BlueprintNotFoundError):
            return blueprint_id

    def record_run(
        self,
        prompt_id: str,
        session_id: str,
        status: str,
        started_at: datetime,
    ) -> None:
        """Record a completed run in the prompt's embedded run_stats."""
        self._repo.record_run(prompt_id, session_id, status, started_at)

    def get(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        return self._load_and_verify(prompt_id, identity)

    def get_runs(
        self, prompt_id: str, *, identity: Identity, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return run history for a scheduled prompt, with ownership verification."""
        self._load_and_verify(prompt_id, identity)
        if not self._session_service:
            return []
        return self._session_service.get_runs_by_schedule(prompt_id, limit=limit)

    def mark_completed(self, prompt_id: str) -> None:
        """Transition a finite schedule to COMPLETED if exhausted.

        Called after every workflow execution.  Uses the same exhaustion
        logic as ``update()`` — compares ``remaining_actions`` against
        ``total_runs`` and checks ``end_at``.
        """
        try:
            prompt = self._repo.load(prompt_id)
        except KeyError:
            logger.warning("mark_completed: prompt %s not found", prompt_id)
            return

        if prompt.schedule_status != ScheduleStatus.ACTIVE:
            return

        if not self._is_schedule_already_exhausted(
            prompt.schedule, prompt.run_stats.total_runs,
        ):
            return

        prompt = prompt.model_copy(update={
            "schedule_status": ScheduleStatus.COMPLETED,
            "completed_at": datetime.now(timezone.utc),
        })
        self._update_or_warn(prompt)

    def _update_or_warn(self, prompt: ScheduledPrompt) -> None:
        """Persist prompt and log a warning if the document was not modified."""
        if not self._repo.update(prompt):
            logger.warning(
                "repo.update returned False for prompt %s — document may have been deleted concurrently",
                prompt.id,
            )

    def _load_and_verify(self, prompt_id: str, identity: Identity) -> ScheduledPrompt:
        try:
            prompt = self._repo.load(prompt_id)
        except KeyError:
            raise PromptNotFoundError(prompt_id)

        if not prompt.identity.owns(identity):
            raise PromptPermissionError(prompt_id, identity)

        return prompt
