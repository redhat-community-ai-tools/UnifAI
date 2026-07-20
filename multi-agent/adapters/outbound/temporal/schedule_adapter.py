"""
Temporal schedule adapter -- implements SchedulePort using Temporal's Schedules API.

Bridges from synchronous Flask context to async Temporal client
using asyncio.run(), same pattern as TemporalSessionEngine.
"""
import asyncio
import logging

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy as TemporalOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
)

from config.app_config import AppConfig
from mas.prompts.models import ScheduleOverlapPolicy, ScheduledPrompt
from mas.prompts.ports import SchedulePort
from temporal.client import get_temporal_client

logger = logging.getLogger(__name__)

_WORKFLOW_NAME = "ScheduledSessionWorkflow"

_OVERLAP_MAP = {
    ScheduleOverlapPolicy.SKIP: TemporalOverlapPolicy.SKIP,
    ScheduleOverlapPolicy.BUFFER_ONE: TemporalOverlapPolicy.BUFFER_ONE,
    ScheduleOverlapPolicy.CANCEL_OTHER: TemporalOverlapPolicy.CANCEL_OTHER,
    ScheduleOverlapPolicy.ALLOW_ALL: TemporalOverlapPolicy.ALLOW_ALL,
}


class TemporalScheduleAdapter(SchedulePort):

    def create_schedule(self, prompt: ScheduledPrompt) -> str:
        return asyncio.run(self._create(prompt))

    def pause(self, temporal_schedule_id: str) -> None:
        asyncio.run(self._pause(temporal_schedule_id))

    def resume(self, temporal_schedule_id: str) -> None:
        asyncio.run(self._resume(temporal_schedule_id))

    def delete(self, temporal_schedule_id: str) -> None:
        asyncio.run(self._delete(temporal_schedule_id))

    async def _create(self, prompt: ScheduledPrompt) -> str:
        from temporal.models import ScheduledSessionParams

        cfg = AppConfig.get_instance()
        client = await get_temporal_client()

        schedule_id = f"sched-{prompt.id}"

        spec = self._build_spec(prompt)
        overlap = _OVERLAP_MAP.get(
            prompt.schedule.overlap_policy, TemporalOverlapPolicy.SKIP
        )

        params = ScheduledSessionParams(
            prompt_id=prompt.id,
            blueprint_id=prompt.blueprint_id,
            identity=prompt.identity,
            text=prompt.text,
            inputs=prompt.inputs,
            source=prompt.source.value,
        )

        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    _WORKFLOW_NAME,
                    params,
                    id=f"sched-wf-{prompt.id}",
                    task_queue=cfg.temporal_task_queue,
                ),
                spec=spec,
                policy=SchedulePolicy(overlap=overlap),
                state=ScheduleState(
                    limited_actions=prompt.schedule.remaining_actions is not None,
                    remaining_actions=prompt.schedule.remaining_actions or 0,
                    paused=not prompt.schedule.enabled,
                ),
            ),
        )
        return schedule_id

    async def _pause(self, temporal_schedule_id: str) -> None:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)
        await handle.pause()

    async def _resume(self, temporal_schedule_id: str) -> None:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)
        await handle.unpause()

    async def _delete(self, temporal_schedule_id: str) -> None:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)
        await handle.delete()

    @staticmethod
    def _build_spec(prompt: ScheduledPrompt) -> ScheduleSpec:
        sched = prompt.schedule
        kwargs: dict = {}

        if sched.interval:
            offset = None
            if sched.start_at:
                total_seconds = int(sched.interval.total_seconds())
                if total_seconds > 0:
                    from datetime import timedelta, timezone as tz
                    epoch_seconds = int(sched.start_at.replace(tzinfo=tz.utc).timestamp()
                                        if sched.start_at.tzinfo is None
                                        else sched.start_at.timestamp())
                    offset = timedelta(seconds=epoch_seconds % total_seconds)
            kwargs["intervals"] = [
                ScheduleIntervalSpec(every=sched.interval, offset=offset)
            ]
        elif sched.cron_expression:
            kwargs["cron_expressions"] = [sched.cron_expression]

        if sched.start_at:
            kwargs["start_at"] = sched.start_at
        if sched.end_at:
            kwargs["end_at"] = sched.end_at
        if sched.timezone:
            kwargs["time_zone_name"] = sched.timezone

        spec = ScheduleSpec(**kwargs)
        return spec
