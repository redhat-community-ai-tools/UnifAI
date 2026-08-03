"""Unit tests for TemporalScheduleAdapter.

Covers: create_schedule, pause, resume, delete, trigger_now, _build_spec.
(Test Plan section 4.1–4.2)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest

from mas.core.identity import Identity
from mas.scheduling.models import (
    ScheduleDefinition,
    ScheduleOverlapPolicy,
    WorkflowSchedule,
)


def _make_prompt(
    interval=None, cron=None, remaining_actions=None,
    start_at=None, end_at=None, timezone_str="UTC",
    overlap=ScheduleOverlapPolicy.SKIP, enabled=True,
):
    sched_kwargs = {"timezone": timezone_str, "overlap_policy": overlap, "enabled": enabled}
    if interval:
        sched_kwargs["interval"] = interval
    if cron:
        sched_kwargs["cron_expression"] = cron
    if remaining_actions is not None:
        sched_kwargs["remaining_actions"] = remaining_actions
    if start_at:
        sched_kwargs["start_at"] = start_at
    if end_at:
        sched_kwargs["end_at"] = end_at

    return WorkflowSchedule(
        id="prompt-abc",
        blueprint_id="bp-1",
        identity=Identity.user("user-1"),
        text="test",
        schedule=ScheduleDefinition(**sched_kwargs),
    )


class TestBuildSpec:
    """Tests for the static _build_spec method without needing Temporal client."""

    @pytest.fixture(autouse=True)
    def import_adapter(self):
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        self.adapter_cls = TemporalScheduleAdapter

    def test_interval_spec_created(self):
        prompt = _make_prompt(interval=timedelta(minutes=15))
        spec = self.adapter_cls._build_spec(prompt)
        assert len(spec.intervals) == 1
        assert spec.intervals[0].every == timedelta(minutes=15)
        assert spec.cron_expressions == []

    def test_cron_spec_created(self):
        prompt = _make_prompt(cron="0 6 * * *")
        spec = self.adapter_cls._build_spec(prompt)
        assert spec.cron_expressions == ["0 6 * * *"]
        assert spec.intervals == []

    def test_schedule_id_format(self):
        prompt = _make_prompt(interval=timedelta(hours=1))
        assert f"sched-{prompt.id}" == "sched-prompt-abc"

    def test_workflow_id_format(self):
        prompt = _make_prompt(interval=timedelta(hours=1))
        assert f"sched-wf-{prompt.id}" == "sched-wf-prompt-abc"

    def test_start_at_passed(self):
        start = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
        prompt = _make_prompt(interval=timedelta(hours=1), start_at=start)
        spec = self.adapter_cls._build_spec(prompt)
        assert spec.start_at == start

    def test_end_at_passed(self):
        end = datetime(2026, 12, 31, tzinfo=timezone.utc)
        prompt = _make_prompt(interval=timedelta(hours=1), end_at=end)
        spec = self.adapter_cls._build_spec(prompt)
        assert spec.end_at == end

    def test_timezone_as_time_zone_name(self):
        prompt = _make_prompt(interval=timedelta(hours=1), timezone_str="America/New_York")
        spec = self.adapter_cls._build_spec(prompt)
        assert spec.time_zone_name == "America/New_York"

    def test_interval_offset_from_start_at(self):
        start = datetime(2026, 7, 20, 9, 37, 0, tzinfo=timezone.utc)
        interval = timedelta(hours=1)
        prompt = _make_prompt(interval=interval, start_at=start)
        spec = self.adapter_cls._build_spec(prompt)
        epoch_seconds = int(start.timestamp())
        expected_offset = timedelta(seconds=epoch_seconds % 3600)
        assert spec.intervals[0].offset == expected_offset

    def test_interval_without_start_at_no_offset(self):
        prompt = _make_prompt(interval=timedelta(hours=1))
        spec = self.adapter_cls._build_spec(prompt)
        assert spec.intervals[0].offset is None


class TestOverlapMapping:
    @pytest.fixture(autouse=True)
    def import_module(self):
        from outbound.temporal.schedule_adapter import _OVERLAP_MAP
        from temporalio.client import ScheduleOverlapPolicy as TemporalOverlapPolicy
        self.overlap_map = _OVERLAP_MAP
        self.temporal_enum = TemporalOverlapPolicy

    def test_skip_maps(self):
        assert self.overlap_map[ScheduleOverlapPolicy.SKIP] == self.temporal_enum.SKIP

    def test_buffer_one_maps(self):
        assert self.overlap_map[ScheduleOverlapPolicy.BUFFER_ONE] == self.temporal_enum.BUFFER_ONE

    def test_cancel_other_maps(self):
        assert self.overlap_map[ScheduleOverlapPolicy.CANCEL_OTHER] == self.temporal_enum.CANCEL_OTHER

    def test_allow_all_not_a_valid_member(self):
        """ALLOW_ALL is intentionally not a ScheduleOverlapPolicy member -- disallowed
        until a proper concurrency policy is designed."""
        assert not hasattr(ScheduleOverlapPolicy, "ALLOW_ALL")


class TestScheduleState:
    """Verify remaining_actions → ScheduleState mapping logic."""

    @pytest.fixture(autouse=True)
    def import_adapter(self):
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        self.adapter_cls = TemporalScheduleAdapter

    def test_remaining_actions_set(self):
        prompt = _make_prompt(interval=timedelta(hours=1), remaining_actions=1)
        assert prompt.schedule.remaining_actions == 1

    def test_unlimited_schedule(self):
        prompt = _make_prompt(interval=timedelta(hours=1))
        assert prompt.schedule.remaining_actions is None


class TestDescribe:
    """Tests for the describe() method that reads back schedule state."""

    @pytest.fixture(autouse=True)
    def import_adapter(self):
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        self.adapter_cls = TemporalScheduleAdapter

    @staticmethod
    def _mock_client_with_state(*, limited_actions, remaining_actions, paused):
        """Build an AsyncMock client whose schedule handle returns the given state."""
        state = Mock()
        state.limited_actions = limited_actions
        state.remaining_actions = remaining_actions
        state.paused = paused

        schedule = Mock()
        schedule.state = state

        desc_result = Mock()
        desc_result.schedule = schedule

        handle = Mock()
        handle.describe = AsyncMock(return_value=desc_result)

        client = Mock()
        client.get_schedule_handle = Mock(return_value=handle)
        return client

    def test_describe_exhausted_schedule(self):
        """limited_actions=True + remaining_actions=0 → running=False."""
        from mas.scheduling.ports import ScheduleInfo

        client = self._mock_client_with_state(
            limited_actions=True, remaining_actions=0, paused=False,
        )
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            info = adapter.describe("sched-test")

        assert info == ScheduleInfo(paused=False, remaining_actions=0, running=False)

    def test_describe_running_finite_schedule(self):
        """limited_actions=True + remaining_actions > 0 → running=True."""
        from mas.scheduling.ports import ScheduleInfo

        client = self._mock_client_with_state(
            limited_actions=True, remaining_actions=2, paused=False,
        )
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            info = adapter.describe("sched-test")

        assert info == ScheduleInfo(paused=False, remaining_actions=2, running=True)

    def test_describe_unlimited_schedule(self):
        """limited_actions=False → remaining_actions=None, running=True."""
        from mas.scheduling.ports import ScheduleInfo

        client = self._mock_client_with_state(
            limited_actions=False, remaining_actions=0, paused=False,
        )
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            info = adapter.describe("sched-test")

        assert info == ScheduleInfo(paused=False, remaining_actions=None, running=True)

    def test_describe_not_found_raises(self):
        """RPCError NOT_FOUND → ScheduleNotFoundError."""
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")

        handle = Mock()
        handle.describe = AsyncMock(side_effect=rpc_error)

        client = Mock()
        client.get_schedule_handle = Mock(return_value=handle)

        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.describe("sched-gone")

    def test_describe_paused_schedule(self):
        """Paused schedule → paused=True, running still reflects actions state."""
        from mas.scheduling.ports import ScheduleInfo

        client = self._mock_client_with_state(
            limited_actions=True, remaining_actions=5, paused=True,
        )
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            info = adapter.describe("sched-test")

        assert info == ScheduleInfo(paused=True, remaining_actions=5, running=True)


class TestCreateUpdateErrorTranslation:
    """RPCError(INVALID_ARGUMENT) from Temporal is translated to ScheduleValidationError
    so malformed schedules surface as clean validation errors rather than raw RPC failures."""

    @pytest.fixture(autouse=True)
    def import_adapter(self):
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        self.adapter_cls = TemporalScheduleAdapter

    def test_create_schedule_invalid_argument_translated(self):
        from mas.scheduling.ports import ScheduleValidationError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("bad cron", RPCStatusCode.INVALID_ARGUMENT, b"")
        client = Mock()
        client.create_schedule = AsyncMock(side_effect=rpc_error)

        prompt = _make_prompt(interval=timedelta(minutes=5))
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleValidationError):
                adapter.create_schedule(prompt)

    def test_create_schedule_other_rpc_error_translated(self):
        from mas.scheduling.ports import ScheduleEngineError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("unavailable", RPCStatusCode.UNAVAILABLE, b"")
        client = Mock()
        client.create_schedule = AsyncMock(side_effect=rpc_error)

        prompt = _make_prompt(interval=timedelta(minutes=5))
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleEngineError, match="unavailable"):
                adapter.create_schedule(prompt)

    def test_update_schedule_invalid_argument_translated(self):
        from mas.scheduling.ports import ScheduleValidationError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("bad timezone", RPCStatusCode.INVALID_ARGUMENT, b"")
        handle = Mock()
        handle.update = AsyncMock(side_effect=rpc_error)
        client = Mock()
        client.get_schedule_handle = Mock(return_value=handle)

        prompt = _make_prompt(interval=timedelta(minutes=5))
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleValidationError):
                adapter.update_schedule("sched-1", prompt)

    def test_update_schedule_not_found_translated(self):
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        handle = Mock()
        handle.update = AsyncMock(side_effect=rpc_error)
        client = Mock()
        client.get_schedule_handle = Mock(return_value=handle)

        prompt = _make_prompt(interval=timedelta(minutes=5))
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.update_schedule("sched-gone", prompt)


class TestLifecycleNotFoundTranslation:
    """RPCError(NOT_FOUND) on pause/resume/trigger/delete → ScheduleNotFoundError
    so service-layer drift handling can catch a typed port error."""

    @pytest.fixture(autouse=True)
    def import_adapter(self):
        from outbound.temporal.schedule_adapter import TemporalScheduleAdapter
        self.adapter_cls = TemporalScheduleAdapter

    @staticmethod
    def _client_with_handle_method(method_name: str, side_effect):
        handle = Mock()
        setattr(handle, method_name, AsyncMock(side_effect=side_effect))
        client = Mock()
        client.get_schedule_handle = Mock(return_value=handle)
        return client

    def test_pause_not_found_translated(self):
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        client = self._client_with_handle_method("pause", rpc_error)
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.pause("sched-gone")

    def test_resume_not_found_translated(self):
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        client = self._client_with_handle_method("unpause", rpc_error)
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.resume("sched-gone")

    def test_trigger_not_found_translated(self):
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        client = self._client_with_handle_method("trigger", rpc_error)
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.trigger_now("sched-gone")

    def test_delete_not_found_translated(self):
        from mas.scheduling.ports import ScheduleNotFoundError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("not found", RPCStatusCode.NOT_FOUND, b"")
        client = self._client_with_handle_method("delete", rpc_error)
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleNotFoundError):
                adapter.delete("sched-gone")

    def test_pause_other_rpc_error_translated(self):
        from mas.scheduling.ports import ScheduleEngineError
        from temporalio.service import RPCError, RPCStatusCode

        rpc_error = RPCError("unavailable", RPCStatusCode.UNAVAILABLE, b"")
        client = self._client_with_handle_method("pause", rpc_error)
        adapter = self.adapter_cls()
        with patch(
            "outbound.temporal.schedule_adapter.get_temporal_client",
            new_callable=AsyncMock, return_value=client,
        ):
            with pytest.raises(ScheduleEngineError, match="unavailable"):
                adapter.pause("sched-1")
