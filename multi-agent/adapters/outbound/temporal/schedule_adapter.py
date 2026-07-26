"""
Temporal schedule adapter -- implements SchedulePort using Temporal's Schedules API.

Bridges from synchronous Flask context to async Temporal client
using asyncio.run(), same pattern as TemporalSessionEngine.
"""
import asyncio
import logging
from datetime import timedelta, timezone

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy as TemporalOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from config.app_config import AppConfig
from temporalio.service import RPCError, RPCStatusCode

from mas.prompts.models import ScheduleOverlapPolicy, ScheduledPrompt
from mas.prompts.ports import BatchDescribeResult, ScheduleDescribeError, ScheduleInfo, ScheduleNotFoundError, SchedulePort
from temporal.client import get_temporal_client
from temporal.models import ScheduledSessionParams

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
        try:
            asyncio.run(self._delete(temporal_schedule_id))
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                raise ScheduleNotFoundError(temporal_schedule_id) from exc
            raise

    def update_schedule(self, temporal_schedule_id: str, prompt: ScheduledPrompt) -> None:
        asyncio.run(self._update(temporal_schedule_id, prompt))

    def trigger_now(self, temporal_schedule_id: str) -> None:
        asyncio.run(self._trigger(temporal_schedule_id))

    def describe(self, temporal_schedule_id: str) -> ScheduleInfo:
        try:
            return asyncio.run(self._describe(temporal_schedule_id))
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                raise ScheduleNotFoundError(temporal_schedule_id) from exc
            raise ScheduleDescribeError(temporal_schedule_id) from exc

    def describe_batch(self, schedule_ids: list[str]) -> BatchDescribeResult:
        return asyncio.run(self._describe_batch(schedule_ids))

    async def _create(self, prompt: ScheduledPrompt) -> str:
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
            credential_user_id=prompt.credential_user_id,
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

    async def _update(self, temporal_schedule_id: str, prompt: ScheduledPrompt) -> None:
        cfg = AppConfig.get_instance()
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)

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
            credential_user_id=prompt.credential_user_id,
        )

        async def _updater(_input: ScheduleUpdateInput) -> ScheduleUpdate:
            return ScheduleUpdate(
                schedule=Schedule(
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
                )
            )

        await handle.update(_updater)

    async def _trigger(self, temporal_schedule_id: str) -> None:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)
        await handle.trigger()

    async def _describe(self, temporal_schedule_id: str) -> ScheduleInfo:
        client = await get_temporal_client()
        handle = client.get_schedule_handle(temporal_schedule_id)
        desc = await handle.describe()
        state = desc.schedule.state
        exhausted = (
            (state.limited_actions and state.remaining_actions == 0)
            or not desc.info.next_action_times
        )
        return ScheduleInfo(
            paused=state.paused,
            remaining_actions=state.remaining_actions if state.limited_actions else None,
            running=not exhausted,
        )

    async def _describe_batch(self, schedule_ids: list[str]) -> BatchDescribeResult:
        """Concurrently describe multiple schedules in a single event loop."""
        client = await get_temporal_client()

        _ERRORED = object()

        async def _describe_one(sid: str) -> tuple[str, ScheduleInfo | None | object]:
            try:
                handle = client.get_schedule_handle(sid)
                desc = await handle.describe()
                state = desc.schedule.state
                exhausted = (
                    (state.limited_actions and state.remaining_actions == 0)
                    or not desc.info.next_action_times
                )
                return sid, ScheduleInfo(
                    paused=state.paused,
                    remaining_actions=state.remaining_actions if state.limited_actions else None,
                    running=not exhausted,
                )
            except RPCError as exc:
                if exc.status == RPCStatusCode.NOT_FOUND:
                    return sid, None
                logger.debug("describe_batch: RPC error for %s: %s", sid, exc)
                return sid, _ERRORED

        raw_results = await asyncio.gather(*[_describe_one(sid) for sid in schedule_ids])

        found: dict[str, ScheduleInfo | None] = {}
        errored: set[str] = set()
        for sid, info in raw_results:
            if info is _ERRORED:
                errored.add(sid)
            else:
                found[sid] = info  # type: ignore[assignment]
        return BatchDescribeResult(found=found, errored=frozenset(errored))

    @staticmethod
    def _build_spec(prompt: ScheduledPrompt) -> ScheduleSpec:
        sched = prompt.schedule
        kwargs: dict = {}

        if sched.interval:
            offset = None
            if sched.start_at:
                total_seconds = int(sched.interval.total_seconds())
                if total_seconds > 0:
                    epoch_seconds = int(sched.start_at.replace(tzinfo=timezone.utc).timestamp()
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
