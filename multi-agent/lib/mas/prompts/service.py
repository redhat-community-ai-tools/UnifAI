"""
Prompt service -- application layer orchestrating prompt CRUD and schedule lifecycle.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mas.core.identity import Identity
from mas.prompts.models import (
    PromptSource,
    ScheduleDefinition,
    ScheduleStatus,
    ScheduledPrompt,
)
from mas.prompts.ports import SchedulePort
from mas.prompts.repository import ScheduledPromptRepository

logger = logging.getLogger(__name__)

MAX_ACTIVE_PROMPTS_PER_BLUEPRINT = 10


class PromptNotFoundError(Exception):
    def __init__(self, prompt_id: str):
        self.prompt_id = prompt_id
        super().__init__(f"Scheduled prompt not found: {prompt_id}")


class PromptLimitExceededError(Exception):
    def __init__(self, blueprint_id: str, limit: int):
        self.blueprint_id = blueprint_id
        self.limit = limit
        super().__init__(
            f"Blueprint {blueprint_id} already has {limit} active scheduled prompts"
        )


class PromptPermissionError(Exception):
    def __init__(self, prompt_id: str, identity: Identity):
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
        blueprint_service,
    ):
        self._repo = prompt_repo
        self._schedule_port = schedule_port
        self._blueprint_service = blueprint_service

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
        if not self._blueprint_service.exists(blueprint_id):
            from mas.session.domain.exceptions import BlueprintNotFoundError
            raise BlueprintNotFoundError(blueprint_id)

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
            self._repo.update(prompt)

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

        if updates:
            prompt = prompt.model_copy(update=updates)

        if schedule_changed and self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.delete(prompt.temporal_schedule_id)
            new_temporal_id = self._schedule_port.create_schedule(prompt)
            prompt = prompt.model_copy(update={"temporal_schedule_id": new_temporal_id})

        self._repo.update(prompt)
        return prompt

    def pause(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.pause(prompt.temporal_schedule_id)

        prompt = prompt.model_copy(update={"schedule_status": ScheduleStatus.PAUSED})
        self._repo.update(prompt)
        return prompt

    def resume(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            self._schedule_port.resume(prompt.temporal_schedule_id)

        prompt = prompt.model_copy(update={"schedule_status": ScheduleStatus.ACTIVE})
        self._repo.update(prompt)
        return prompt

    def delete(self, prompt_id: str, *, identity: Identity) -> None:
        prompt = self._load_and_verify(prompt_id, identity)

        if self._schedule_port and prompt.temporal_schedule_id:
            try:
                self._schedule_port.delete(prompt.temporal_schedule_id)
            except Exception:
                logger.warning(
                    "Failed to delete Temporal schedule %s for prompt %s",
                    prompt.temporal_schedule_id,
                    prompt_id,
                    exc_info=True,
                )

        self._repo.delete(prompt_id)

    def list(self, *, identity: Identity) -> List[ScheduledPrompt]:
        return self._repo.list_by_identity(identity)

    def get(self, prompt_id: str, *, identity: Identity) -> ScheduledPrompt:
        return self._load_and_verify(prompt_id, identity)

    def mark_completed(self, prompt_id: str) -> None:
        try:
            prompt = self._repo.load(prompt_id)
        except KeyError:
            logger.warning("mark_completed: prompt %s not found", prompt_id)
            return

        prompt = prompt.model_copy(update={
            "schedule_status": ScheduleStatus.COMPLETED,
            "completed_at": datetime.now(timezone.utc),
        })
        self._repo.update(prompt)

    def _load_and_verify(self, prompt_id: str, identity: Identity) -> ScheduledPrompt:
        try:
            prompt = self._repo.load(prompt_id)
        except KeyError:
            raise PromptNotFoundError(prompt_id)

        if prompt.identity != identity:
            raise PromptPermissionError(prompt_id, identity)

        return prompt
