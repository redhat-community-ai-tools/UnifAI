"""Unit tests for Scheduled Prompt domain models.

Covers: BasePrompt, ScheduleDefinition, RunStatusEntry, RunStats, WorkflowSchedule.
(Test Plan sections 1.1, 1.3, 1.4, 1.5)
"""
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from mas.core.identity import Identity
from mas.core.prompt import BasePrompt
from mas.scheduling.models import (
    PromptSource,
    RunOutcome,
    RunStats,
    RunStatusEntry,
    ScheduleDefinition,
    ScheduleOverlapPolicy,
    ScheduleStatus,
    WorkflowSchedule,
)


# ═══════════════════════════════════════════════════════════════════
# 1.1 BasePrompt
# ═══════════════════════════════════════════════════════════════════

class TestBasePrompt:
    def test_valid_prompt_creation(self):
        p = BasePrompt(text="hello")
        UUID(p.id)  # valid UUID
        assert p.text == "hello"

    def test_text_whitespace_stripping(self):
        p = BasePrompt(text="  spaced  ")
        assert p.text == "spaced"

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            BasePrompt(text="")

    def test_whitespace_only_text_rejected(self):
        with pytest.raises(ValidationError, match="must not be empty"):
            BasePrompt(text="   \n\t  ")

    def test_default_uuid_generation_unique(self):
        p1 = BasePrompt(text="a")
        p2 = BasePrompt(text="b")
        assert p1.id != p2.id


# ═══════════════════════════════════════════════════════════════════
# 1.3 ScheduleDefinition
# ═══════════════════════════════════════════════════════════════════

class TestScheduleDefinition:
    def test_valid_interval_schedule(self):
        sd = ScheduleDefinition(interval=timedelta(minutes=15))
        assert sd.interval == timedelta(minutes=15)
        assert sd.cron_expression is None

    def test_valid_cron_schedule(self):
        sd = ScheduleDefinition(cron_expression="0 6 * * *")
        assert sd.cron_expression == "0 6 * * *"
        assert sd.interval is None

    def test_neither_interval_nor_cron_rejected(self):
        with pytest.raises(ValidationError, match="Either interval or cron_expression is required"):
            ScheduleDefinition()

    def test_both_interval_and_cron_rejected(self):
        with pytest.raises(ValidationError, match="Specify interval or cron_expression, not both"):
            ScheduleDefinition(interval=timedelta(minutes=5), cron_expression="0 * * * *")

    def test_default_overlap_policy(self):
        sd = ScheduleDefinition(interval=timedelta(minutes=15))
        assert sd.overlap_policy == ScheduleOverlapPolicy.SKIP

    def test_custom_timezone(self):
        sd = ScheduleDefinition(interval=timedelta(hours=1), timezone="America/New_York")
        assert sd.timezone == "America/New_York"

    def test_remaining_actions_one(self):
        sd = ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1)
        assert sd.remaining_actions == 1

    def test_remaining_actions_zero(self):
        sd = ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=0)
        assert sd.remaining_actions == 0

    def test_end_at_in_past_accepted(self):
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        sd = ScheduleDefinition(interval=timedelta(hours=1), end_at=past)
        assert sd.end_at == past

    def test_start_at_after_end_at_rejected(self):
        start = datetime(2030, 1, 1, tzinfo=timezone.utc)
        end = datetime(2020, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValidationError, match="start_at must be before end_at"):
            ScheduleDefinition(interval=timedelta(hours=1), start_at=start, end_at=end)

    def test_frozen_model_immutability(self):
        sd = ScheduleDefinition(interval=timedelta(minutes=5))
        with pytest.raises(ValidationError):
            sd.interval = timedelta(minutes=10)

    def test_sub_minute_interval_rejected(self):
        with pytest.raises(ValidationError, match="interval must be at least"):
            ScheduleDefinition(interval=timedelta(seconds=1))

    def test_interval_just_below_minimum_rejected(self):
        with pytest.raises(ValidationError, match="interval must be at least"):
            ScheduleDefinition(interval=timedelta(seconds=59))

    def test_minimum_interval_boundary_accepted(self):
        sd = ScheduleDefinition(interval=timedelta(minutes=1))
        assert sd.interval == timedelta(minutes=1)

    def test_cron_with_wrong_field_count_rejected(self):
        with pytest.raises(ValidationError, match="cron_expression must be a 5-field"):
            ScheduleDefinition(cron_expression="not-a-cron")

    def test_cron_with_too_few_fields_rejected(self):
        with pytest.raises(ValidationError, match="cron_expression must be a 5-field"):
            ScheduleDefinition(cron_expression="0 6 * *")

    def test_cron_with_invalid_characters_rejected(self):
        with pytest.raises(ValidationError, match="cron_expression must be a 5-field"):
            ScheduleDefinition(cron_expression="0 6 * * ; rm -rf")

    def test_cron_with_named_weekday_accepted(self):
        sd = ScheduleDefinition(cron_expression="0 6 * * MON,WED,FRI")
        assert sd.cron_expression == "0 6 * * MON,WED,FRI"

    def test_invalid_timezone_rejected(self):
        with pytest.raises(ValidationError, match="Unknown timezone"):
            ScheduleDefinition(interval=timedelta(hours=1), timezone="Mars/Phobos")

    def test_valid_iana_timezone_accepted(self):
        sd = ScheduleDefinition(interval=timedelta(hours=1), timezone="Asia/Tokyo")
        assert sd.timezone == "Asia/Tokyo"


# ═══════════════════════════════════════════════════════════════════
# 1.4 RunStats & RunStatusEntry
# ═══════════════════════════════════════════════════════════════════

class TestRunStatusEntry:
    def test_valid_creation(self):
        entry = RunStatusEntry(
            session_id="sess-123",
            status="COMPLETED",
            started_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
        )
        assert entry.session_id == "sess-123"
        assert entry.status == "COMPLETED"
        assert entry.started_at is not None

    def test_frozen_model(self):
        entry = RunStatusEntry(session_id="s", status=RunOutcome.COMPLETED)
        with pytest.raises(ValidationError):
            entry.status = RunOutcome.FAILED

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            RunStatusEntry(session_id="s", status="OK")


class TestRunStats:
    def test_default_values(self):
        rs = RunStats()
        assert rs.total_runs == 0
        assert rs.last_run_at is None
        assert rs.recent_statuses == []

    def test_serialization_json(self):
        now = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
        entry = RunStatusEntry(session_id="s1", status="COMPLETED", started_at=now)
        rs = RunStats(total_runs=3, last_run_at=now, recent_statuses=[entry])
        dumped = rs.model_dump(mode="json")
        assert dumped["total_runs"] == 3
        assert "last_run_at" in dumped
        assert len(dumped["recent_statuses"]) == 1


# ═══════════════════════════════════════════════════════════════════
# 1.5 WorkflowSchedule
# ═══════════════════════════════════════════════════════════════════

class TestWorkflowSchedule:
    @pytest.fixture
    def identity(self):
        return Identity.user("user-1")

    @pytest.fixture
    def schedule(self):
        return ScheduleDefinition(interval=timedelta(minutes=15))

    def test_valid_creation(self, identity, schedule):
        p = WorkflowSchedule(
            blueprint_id="bp-1",
            identity=identity,
            inputs={"user_prompt": "test prompt"},
            schedule=schedule,
        )
        UUID(p.id)
        assert p.schedule_status == ScheduleStatus.ACTIVE
        assert p.completed_at is None
        assert p.run_stats.total_runs == 0

    def test_requires_non_empty_user_prompt(self, identity, schedule):
        with pytest.raises(ValidationError, match="must not be empty"):
            WorkflowSchedule(
                blueprint_id="bp-1",
                identity=identity,
                inputs={"user_prompt": ""},
                schedule=schedule,
            )

    def test_default_source_is_manual(self, identity, schedule):
        p = WorkflowSchedule(
            blueprint_id="bp-1", identity=identity, inputs={"user_prompt": "x"}, schedule=schedule,
        )
        assert p.source == PromptSource.MANUAL

    def test_source_shortcut_copy(self, identity, schedule):
        p = WorkflowSchedule(
            blueprint_id="bp-1",
            identity=identity,
            inputs={"user_prompt": "x"},
            schedule=schedule,
            source=PromptSource.SHORTCUT_COPY,
        )
        assert p.source == PromptSource.SHORTCUT_COPY

    def test_missing_user_prompt_rejected(self, identity, schedule):
        with pytest.raises(ValidationError, match="user_prompt"):
            WorkflowSchedule(
                blueprint_id="bp-1", identity=identity, inputs={}, schedule=schedule,
            )

    def test_complex_inputs(self, identity, schedule):
        inputs = {"user_prompt": "x", "key": [1, 2, 3], "nested": {"a": "b"}}
        p = WorkflowSchedule(
            blueprint_id="bp-1",
            identity=identity,
            schedule=schedule,
            inputs=inputs,
        )
        assert p.inputs == inputs

    def test_model_dump_json_roundtrip(self, identity, schedule):
        p = WorkflowSchedule(
            blueprint_id="bp-1", identity=identity, inputs={"user_prompt": "hello"}, schedule=schedule,
        )
        dumped = p.model_dump(mode="json")
        reconstructed = WorkflowSchedule(**dumped)
        assert reconstructed.id == p.id
        assert reconstructed.user_prompt == p.user_prompt
        assert reconstructed.blueprint_id == p.blueprint_id
        assert reconstructed.run_stats.total_runs == 0

    def test_identity_field_required(self, schedule):
        with pytest.raises(ValidationError):
            WorkflowSchedule(blueprint_id="bp-1", inputs={"user_prompt": "x"}, schedule=schedule)

    def test_run_stats_defaults_to_empty(self, identity, schedule):
        p = WorkflowSchedule(
            blueprint_id="bp-1", identity=identity, inputs={"user_prompt": "x"}, schedule=schedule,
        )
        assert p.run_stats.total_runs == 0
        assert p.run_stats.recent_statuses == []
        assert p.run_stats.last_run_at is None
