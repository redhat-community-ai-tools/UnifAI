"""Unit tests for WorkflowScheduleService.

Covers: create, update, pause, resume, trigger, delete, list, list_enriched,
        get, get_runs, record_run, mark_completed.
(Test Plan sections 3.1–3.8)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import ANY, Mock, MagicMock, patch, call

import pytest

from mas.core.identity import Identity
from mas.scheduling.models import (
    PromptSource,
    RunStats,
    ScheduleDefinition,
    ScheduleOverlapPolicy,
    ScheduleStatus,
    WorkflowSchedule,
)
from mas.scheduling.noop import NoOpScheduleEngine
from mas.scheduling.ports import ScheduleNotFoundError as EngineScheduleNotFoundError, ScheduleValidationError
from mas.scheduling.service import (
    MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT,
    ScheduleLimitExceededError,
    ScheduleNotFoundError,
    SchedulePermissionError,
    WorkflowScheduleService,
)


@pytest.fixture
def identity_a():
    return Identity.user("user-a")


@pytest.fixture
def identity_b():
    return Identity.user("user-b")


@pytest.fixture
def team_identity():
    return Identity.team("team-1")


def _make_prompt(identity, blueprint_id="bp-1", status=ScheduleStatus.ACTIVE, **kwargs):
    return WorkflowSchedule(
        blueprint_id=blueprint_id,
        identity=identity,
        text=kwargs.pop("text", "test prompt"),
        schedule=kwargs.pop("schedule", ScheduleDefinition(interval=timedelta(minutes=15))),
        schedule_status=status,
        **kwargs,
    )


@pytest.fixture
def mock_repo():
    repo = Mock()
    repo.save.return_value = "prompt-id"
    repo.update.return_value = True
    repo.delete.return_value = True
    repo.count_active_by_blueprint.return_value = 0
    return repo


@pytest.fixture
def mock_schedule_port():
    from mas.scheduling.ports import BatchDescribeResult
    port = Mock()
    port.create_schedule.return_value = "sched-prompt-id"
    port.describe_batch.return_value = BatchDescribeResult(found={}, errored=frozenset())
    return port


@pytest.fixture
def mock_blueprint_service(identity_a):
    svc = Mock()
    svc.exists.return_value = True
    doc = Mock()
    doc.spec_dict = {"name": "My Blueprint"}
    doc.identity = identity_a
    svc.get_blueprint_draft_doc.return_value = doc
    return svc


@pytest.fixture
def mock_session_service():
    svc = Mock()
    svc.get_runs_by_schedule.return_value = []
    return svc


@pytest.fixture
def service(mock_repo, mock_schedule_port, mock_blueprint_service, mock_session_service):
    return WorkflowScheduleService(
        schedule_repo=mock_repo,
        schedule_engine=mock_schedule_port,
        blueprint_service=mock_blueprint_service,
        session_service=mock_session_service,
    )


# ═══════════════════════════════════════════════════════════════════
# 3.1 Create Flow
# ═══════════════════════════════════════════════════════════════════

class TestServiceCreate:
    def test_happy_path_interval(self, service, mock_repo, mock_schedule_port, identity_a):
        result = service.create(
            identity=identity_a,
            blueprint_id="bp-1",
            text="Generate report",
            schedule={"interval": "PT900S"},
        )
        assert result.schedule_status == ScheduleStatus.ACTIVE
        assert result.engine_handle == "sched-prompt-id"
        mock_repo.save.assert_called_once()
        mock_schedule_port.create_schedule.assert_called_once()
        mock_repo.update.assert_called_once()

    def test_happy_path_cron(self, service, identity_a):
        result = service.create(
            identity=identity_a,
            blueprint_id="bp-1",
            text="Generate report",
            schedule={"cron_expression": "0 * * * *"},
        )
        assert result.schedule.cron_expression == "0 * * * *"

    def test_blueprint_not_found(self, service, mock_blueprint_service, identity_a):
        from mas.blueprints.exceptions import BlueprintNotFoundError
        mock_blueprint_service.get_blueprint_draft_doc.side_effect = KeyError("nonexistent")
        with pytest.raises(BlueprintNotFoundError):
            service.create(
                identity=identity_a,
                blueprint_id="nonexistent",
                text="x",
                schedule={"interval": "PT60S"},
            )
        mock_blueprint_service.get_blueprint_draft_doc.side_effect = None

    def test_per_blueprint_limit_exceeded(self, service, mock_repo, identity_a):
        mock_repo.count_active_by_blueprint.return_value = MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT
        with pytest.raises(ScheduleLimitExceededError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={"interval": "PT60S"},
            )

    def test_paused_counts_toward_limit(self, service, mock_repo, identity_a):
        mock_repo.count_active_by_blueprint.return_value = MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT
        with pytest.raises(ScheduleLimitExceededError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={"interval": "PT60S"},
            )

    def test_completed_do_not_count_toward_limit(self, service, mock_repo, identity_a):
        mock_repo.count_active_by_blueprint.return_value = MAX_ACTIVE_SCHEDULES_PER_BLUEPRINT - 1
        result = service.create(
            identity=identity_a,
            blueprint_id="bp-1",
            text="x",
            schedule={"interval": "PT60S"},
        )
        assert result is not None

    def test_invalid_schedule_definition(self, service, identity_a):
        with pytest.raises(ValueError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={},
            )

    def test_invalid_source_value(self, service, identity_a):
        with pytest.raises(ValueError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                source="invalid_source",
                schedule={"interval": "PT60S"},
            )

    def test_noop_engine_rejects_create(self, mock_repo, mock_blueprint_service, identity_a):
        svc = WorkflowScheduleService(
            schedule_repo=mock_repo,
            schedule_engine=NoOpScheduleEngine(),
            blueprint_service=mock_blueprint_service,
        )
        with pytest.raises(ScheduleValidationError, match="no engine configured"):
            svc.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={"interval": "PT60S"},
            )
        mock_repo.delete.assert_called_once()

    def test_temporal_fails_after_save(self, service, mock_schedule_port, mock_repo, identity_a):
        mock_schedule_port.create_schedule.side_effect = RuntimeError("Temporal down")
        with pytest.raises(RuntimeError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={"interval": "PT60S"},
            )
        mock_repo.save.assert_called_once()

    def test_source_shortcut_copy(self, service, identity_a):
        result = service.create(
            identity=identity_a,
            blueprint_id="bp-1",
            text="x",
            source="shortcut_copy",
            schedule={"interval": "PT60S"},
        )
        assert result.source == PromptSource.SHORTCUT_COPY

    def test_allow_all_overlap_policy_rejected(self, service, mock_repo, mock_schedule_port, identity_a):
        """ALLOW_ALL is not a valid ScheduleOverlapPolicy member -- construction itself fails."""
        with pytest.raises(ValueError):
            service.create(
                identity=identity_a,
                blueprint_id="bp-1",
                text="x",
                schedule={"interval": "PT60S", "overlap_policy": "allow_all"},
            )
        mock_repo.save.assert_not_called()
        mock_schedule_port.create_schedule.assert_not_called()

    def test_very_long_prompt_text(self, service, identity_a):
        long_text = "x" * 10000
        result = service.create(
            identity=identity_a,
            blueprint_id="bp-1",
            text=long_text,
            schedule={"interval": "PT60S"},
        )
        assert result.text == long_text


# ═══════════════════════════════════════════════════════════════════
# 3.2 Update Flow
# ═══════════════════════════════════════════════════════════════════

class TestServiceUpdate:
    @pytest.fixture(autouse=True)
    def setup(self, mock_repo, identity_a):
        self.existing = _make_prompt(identity_a, engine_handle="sched-old")
        mock_repo.load.return_value = self.existing

    def test_update_text_only(self, service, mock_repo, mock_schedule_port, identity_a):
        result = service.update(self.existing.id, identity=identity_a, text="new text")
        assert result.text == "new text"
        mock_schedule_port.delete.assert_not_called()
        mock_repo.update.assert_called_once()

    def test_update_inputs_only(self, service, mock_repo, identity_a):
        result = service.update(self.existing.id, identity=identity_a, inputs={"k": "v"})
        assert result.inputs == {"k": "v"}

    def test_update_schedule_triggers_atomic_update(self, service, mock_schedule_port, identity_a):
        new_schedule = {"interval": "PT1800S"}
        service.update(
            self.existing.id, identity=identity_a, schedule=new_schedule,
        )
        mock_schedule_port.update_schedule.assert_called_once_with(
            "sched-old", ANY,
        )
        mock_schedule_port.delete.assert_not_called()
        mock_schedule_port.create_schedule.assert_not_called()

    def test_update_schedule_same_value_noop(self, service, mock_schedule_port, identity_a):
        same_schedule = {"interval": "PT900S"}
        service.update(self.existing.id, identity=identity_a, schedule=same_schedule)
        mock_schedule_port.delete.assert_not_called()

    def test_update_nonexistent_prompt(self, service, mock_repo, identity_a):
        mock_repo.load.side_effect = KeyError("not found")
        with pytest.raises(ScheduleNotFoundError):
            service.update("bad-id", identity=identity_a, text="x")

    def test_update_wrong_identity(self, service, identity_b):
        with pytest.raises(SchedulePermissionError):
            service.update(self.existing.id, identity=identity_b, text="x")

    def test_update_all_fields(self, service, mock_schedule_port, identity_a):
        result = service.update(
            self.existing.id,
            identity=identity_a,
            text="new",
            inputs={"a": 1},
            schedule={"cron_expression": "0 6 * * *"},
        )
        assert result.text == "new"
        assert result.inputs == {"a": 1}
        mock_schedule_port.update_schedule.assert_called_once()
        mock_schedule_port.delete.assert_not_called()

    def test_update_no_changes(self, service, mock_repo, identity_a):
        service.update(self.existing.id, identity=identity_a)
        mock_repo.update.assert_called_once()

    def test_update_to_allow_all_overlap_policy_rejected(self, service, mock_repo, mock_schedule_port, identity_a):
        """ALLOW_ALL is not a valid ScheduleOverlapPolicy member -- construction itself fails."""
        with pytest.raises(ValueError):
            service.update(
                self.existing.id,
                identity=identity_a,
                schedule={"interval": "PT900S", "overlap_policy": "allow_all"},
            )
        mock_schedule_port.update_schedule.assert_not_called()
        mock_repo.update.assert_not_called()

    def test_schedule_change_with_noop_engine(
        self, mock_repo, mock_blueprint_service, identity_a,
    ):
        """NoOp engine rejects schedule creation during update sync."""
        existing = _make_prompt(identity_a, engine_handle=None)
        mock_repo.load.return_value = existing
        svc = WorkflowScheduleService(
            schedule_repo=mock_repo,
            schedule_engine=NoOpScheduleEngine(),
            blueprint_service=mock_blueprint_service,
        )
        with pytest.raises(ScheduleValidationError, match="no engine configured"):
            svc.update(existing.id, identity=identity_a, schedule={"interval": "PT3600S"})

    def test_recurrence_only_update_preserves_run_stats_and_start_at(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        start = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)
        existing = _make_prompt(
            identity_a,
            engine_handle="sched-old",
            schedule=ScheduleDefinition(
                interval=timedelta(minutes=15), start_at=start, remaining_actions=10,
            ),
            run_stats=RunStats(total_runs=3),
        )
        mock_repo.load.return_value = existing

        result = service.update(
            existing.id,
            identity=identity_a,
            schedule={"interval": "PT3600S"},  # no start_at — keep existing
        )

        assert result.run_stats.total_runs == 3
        assert result.schedule.start_at == start
        assert result.schedule.remaining_actions == 10
        assert result.schedule.interval == timedelta(hours=1)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_schedule_port.update_schedule.assert_called_once()

    def test_remaining_actions_below_total_runs_rejected(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        existing = _make_prompt(
            identity_a,
            engine_handle="sched-old",
            schedule=ScheduleDefinition(
                interval=timedelta(hours=1), remaining_actions=10,
            ),
            run_stats=RunStats(total_runs=6),
        )
        mock_repo.load.return_value = existing

        with pytest.raises(ValueError, match="Ends after cannot be less"):
            service.update(
                existing.id,
                identity=identity_a,
                schedule={"remaining_actions": 5},
            )
        mock_schedule_port.update_schedule.assert_not_called()
        mock_repo.update.assert_not_called()

    def test_remaining_actions_equal_total_runs_marks_completed(
        self, service, mock_repo, identity_a,
    ):
        """Ends-after == total_runs is valid: schedule has no runs left → COMPLETED."""
        existing = _make_prompt(
            identity_a,
            engine_handle="sched-old",
            schedule=ScheduleDefinition(
                interval=timedelta(hours=1), remaining_actions=10,
            ),
            run_stats=RunStats(total_runs=1),
        )
        mock_repo.load.return_value = existing

        result = service.update(
            existing.id,
            identity=identity_a,
            schedule={"remaining_actions": 1},
        )
        assert result.schedule.remaining_actions == 1
        assert result.run_stats.total_runs == 1
        assert result.schedule_status == ScheduleStatus.COMPLETED
        assert result.completed_at is not None

    def test_remaining_actions_above_total_runs_keeps_run_stats(
        self, service, mock_repo, identity_a,
    ):
        existing = _make_prompt(
            identity_a,
            engine_handle="sched-old",
            schedule=ScheduleDefinition(
                interval=timedelta(hours=1), remaining_actions=10,
            ),
            run_stats=RunStats(total_runs=6),
        )
        mock_repo.load.return_value = existing

        result = service.update(
            existing.id,
            identity=identity_a,
            schedule={"remaining_actions": 8},
        )
        assert result.schedule.remaining_actions == 8
        assert result.run_stats.total_runs == 6
        assert result.schedule_status == ScheduleStatus.ACTIVE

    def test_completed_reactivation_resets_run_stats(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        start = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
        existing = _make_prompt(
            identity_a,
            status=ScheduleStatus.COMPLETED,
            engine_handle="sched-old",
            schedule=ScheduleDefinition(
                interval=timedelta(hours=1), remaining_actions=3, start_at=start,
            ),
            run_stats=RunStats(total_runs=3),
            completed_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        mock_repo.load.return_value = existing

        new_start = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
        result = service.update(
            existing.id,
            identity=identity_a,
            schedule={
                "interval": "PT3600S",
                "remaining_actions": 5,
                "start_at": new_start,
            },
        )
        assert result.schedule_status == ScheduleStatus.ACTIVE
        assert result.completed_at is None
        assert result.run_stats.total_runs == 0
        assert result.schedule.remaining_actions == 5
        mock_schedule_port.update_schedule.assert_called_once()

    def test_engine_missing_on_update_recreates(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        existing = _make_prompt(identity_a, engine_handle="sched-gone")
        mock_repo.load.return_value = existing
        mock_schedule_port.update_schedule.side_effect = EngineScheduleNotFoundError("sched-gone")
        mock_schedule_port.create_schedule.return_value = "sched-new"

        result = service.update(
            existing.id,
            identity=identity_a,
            schedule={"interval": "PT3600S"},
        )
        assert result.engine_handle == "sched-new"
        mock_schedule_port.create_schedule.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 3.3 Pause / Resume
# ═══════════════════════════════════════════════════════════════════

class TestServicePauseResume:
    def test_pause_active(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        result = service.pause(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.PAUSED
        mock_schedule_port.pause.assert_called_once_with("sched-1")

    def test_resume_paused(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(
            identity_a, status=ScheduleStatus.PAUSED, engine_handle="sched-1",
        )
        mock_repo.load.return_value = prompt
        result = service.resume(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_schedule_port.resume.assert_called_once_with("sched-1")

    def test_pause_already_paused_idempotent(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(
            identity_a, status=ScheduleStatus.PAUSED, engine_handle="sched-1",
        )
        mock_repo.load.return_value = prompt
        result = service.pause(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.PAUSED
        mock_schedule_port.pause.assert_called_once()

    def test_resume_already_active_idempotent(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        result = service.resume(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_schedule_port.resume.assert_called_once()

    def test_pause_wrong_identity(self, service, mock_repo, identity_a, identity_b):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.pause(prompt.id, identity=identity_b)

    def test_pause_no_temporal_id(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle=None)
        mock_repo.load.return_value = prompt
        result = service.pause(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.PAUSED
        mock_schedule_port.pause.assert_not_called()

    def test_temporal_pause_fails(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        mock_schedule_port.pause.side_effect = RuntimeError("Temporal error")
        with pytest.raises(RuntimeError):
            service.pause(prompt.id, identity=identity_a)


# ═══════════════════════════════════════════════════════════════════
# 3.4 Delete
# ═══════════════════════════════════════════════════════════════════

class TestServiceDelete:
    def test_delete_active(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        service.delete(prompt.id, identity=identity_a)
        mock_schedule_port.delete.assert_called_once_with("sched-1")
        mock_repo.delete.assert_called_once_with(prompt.id)

    def test_delete_paused(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(
            identity_a, status=ScheduleStatus.PAUSED, engine_handle="sched-1",
        )
        mock_repo.load.return_value = prompt
        service.delete(prompt.id, identity=identity_a)
        mock_schedule_port.delete.assert_called_once()
        mock_repo.delete.assert_called_once()

    def test_delete_wrong_identity(self, service, mock_repo, identity_a, identity_b):
        prompt = _make_prompt(identity_a)
        mock_repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.delete(prompt.id, identity=identity_b)

    def test_schedule_already_removed_still_deletes_from_mongo(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        mock_schedule_port.delete.side_effect = EngineScheduleNotFoundError("sched-1")
        service.delete(prompt.id, identity=identity_a)
        mock_repo.delete.assert_called_once_with(prompt.id)

    def test_unexpected_schedule_error_propagates_on_delete(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        mock_schedule_port.delete.side_effect = RuntimeError("Temporal unavailable")
        with pytest.raises(RuntimeError, match="Temporal unavailable"):
            service.delete(prompt.id, identity=identity_a)

    def test_delete_no_temporal_id(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle=None)
        mock_repo.load.return_value = prompt
        service.delete(prompt.id, identity=identity_a)
        mock_schedule_port.delete.assert_not_called()
        mock_repo.delete.assert_called_once()

    def test_delete_nonexistent(self, service, mock_repo, identity_a):
        mock_repo.load.side_effect = KeyError("nope")
        with pytest.raises(ScheduleNotFoundError):
            service.delete("bad-id", identity=identity_a)


# ═══════════════════════════════════════════════════════════════════
# 3.5 Trigger
# ═══════════════════════════════════════════════════════════════════

class TestServiceTrigger:
    def test_trigger_active(self, service, mock_repo, mock_schedule_port, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        result = service.trigger(prompt.id, identity=identity_a)
        mock_schedule_port.trigger_now.assert_called_once_with("sched-1")
        assert result.id == prompt.id

    def test_trigger_wrong_identity(self, service, mock_repo, identity_a, identity_b):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.trigger(prompt.id, identity=identity_b)

    def test_trigger_noop_engine(self, mock_repo, mock_blueprint_service, identity_a):
        prompt = _make_prompt(identity_a, engine_handle="sched-1")
        mock_repo.load.return_value = prompt
        svc = WorkflowScheduleService(
            schedule_repo=mock_repo, schedule_engine=NoOpScheduleEngine(), blueprint_service=mock_blueprint_service,
        )
        with pytest.raises(ScheduleValidationError, match="no scheduling engine configured"):
            svc.trigger(prompt.id, identity=identity_a)

    def test_trigger_no_temporal_id(self, service, mock_repo, identity_a):
        prompt = _make_prompt(identity_a, engine_handle=None)
        mock_repo.load.return_value = prompt
        with pytest.raises(ValueError, match="no active engine handle"):
            service.trigger(prompt.id, identity=identity_a)

    def test_trigger_nonexistent(self, service, mock_repo, identity_a):
        mock_repo.load.side_effect = KeyError("nope")
        with pytest.raises(ScheduleNotFoundError):
            service.trigger("bad-id", identity=identity_a)


# ═══════════════════════════════════════════════════════════════════
# 3.6 List / Get / List Enriched
# ═══════════════════════════════════════════════════════════════════

class TestServiceListGet:
    def test_list_returns_all_for_identity(self, service, mock_repo, identity_a):
        prompts = [_make_prompt(identity_a) for _ in range(3)]
        mock_repo.list_by_identity.return_value = prompts
        result = service.list(identity=identity_a)
        assert len(result) == 3
        mock_repo.list_by_identity.assert_called_once_with(identity_a)

    def test_get_existing(self, service, mock_repo, identity_a):
        prompt = _make_prompt(identity_a)
        mock_repo.load.return_value = prompt
        result = service.get(prompt.id, identity=identity_a)
        assert result.id == prompt.id

    def test_get_wrong_identity(self, service, mock_repo, identity_a, identity_b):
        prompt = _make_prompt(identity_a)
        mock_repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.get(prompt.id, identity=identity_b)

    def test_get_nonexistent(self, service, mock_repo, identity_a):
        mock_repo.load.side_effect = KeyError("nope")
        with pytest.raises(ScheduleNotFoundError):
            service.get("bad-id", identity=identity_a)

    def test_list_enriched_adds_blueprint_name(
        self, service, mock_repo, mock_blueprint_service, identity_a,
    ):
        prompts = [_make_prompt(identity_a)]
        mock_repo.list_by_identity.return_value = prompts
        result = service.list_enriched(identity=identity_a)
        assert len(result) == 1
        assert result[0]["blueprint_name"] == "My Blueprint"

    def test_list_enriched_with_blueprint_filter(
        self, service, mock_repo, mock_blueprint_service, identity_a,
    ):
        prompts = [_make_prompt(identity_a, blueprint_id="bp-x")]
        mock_repo.find_by_blueprint.return_value = prompts
        result = service.list_enriched(identity=identity_a, blueprint_id="bp-x")
        mock_repo.find_by_blueprint.assert_called_once_with("bp-x")
        assert len(result) == 1

    def test_list_enriched_blueprint_not_found_fallback(
        self, service, mock_repo, mock_blueprint_service, identity_a,
    ):
        prompts = [_make_prompt(identity_a, blueprint_id="deleted-bp")]
        mock_repo.list_by_identity.return_value = prompts
        mock_blueprint_service.get_blueprint_draft_doc.side_effect = KeyError("gone")
        result = service.list_enriched(identity=identity_a)
        assert result[0]["blueprint_name"] == "deleted-bp"

    def test_list_enriched_caches_blueprint_names(
        self, service, mock_repo, mock_blueprint_service, identity_a,
    ):
        p1 = _make_prompt(identity_a, blueprint_id="bp-1")
        p2 = _make_prompt(identity_a, blueprint_id="bp-1")
        p3 = _make_prompt(identity_a, blueprint_id="bp-1")
        mock_repo.list_by_identity.return_value = [p1, p2, p3]
        service.list_enriched(identity=identity_a)
        assert mock_blueprint_service.get_blueprint_draft_doc.call_count == 1


# ═══════════════════════════════════════════════════════════════════
# 3.7 Record Run
# ═══════════════════════════════════════════════════════════════════

class TestServiceRecordRun:
    def test_record_run_delegates_to_repo(self, service, mock_repo):
        now = datetime(2026, 7, 20, tzinfo=timezone.utc)
        service.record_run("prompt-1", "session-1", "COMPLETED", now)
        mock_repo.record_run.assert_called_once_with("prompt-1", "session-1", "COMPLETED", now)


# ═══════════════════════════════════════════════════════════════════
# 3.8 Mark Completed
# ═══════════════════════════════════════════════════════════════════

class TestServiceMarkCompleted:
    def test_mark_finite_prompt_completed_when_exhausted(self, service, mock_repo, identity_a):
        """Prompt with remaining_actions=1 completes when total_runs reaches 1."""
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            run_stats=RunStats(total_runs=1),
        )
        mock_repo.load.return_value = prompt
        service.mark_completed(prompt.id)
        updated = mock_repo.update.call_args[0][0]
        assert updated.schedule_status == ScheduleStatus.COMPLETED
        assert updated.completed_at is not None

    def test_mark_finite_prompt_noop_when_runs_remaining(self, service, mock_repo, identity_a):
        """Prompt with remaining_actions=3 stays ACTIVE at total_runs=1."""
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=3),
            run_stats=RunStats(total_runs=1),
        )
        mock_repo.load.return_value = prompt
        service.mark_completed(prompt.id)
        mock_repo.update.assert_not_called()

    def test_mark_infinite_prompt_noop(self, service, mock_repo, identity_a):
        prompt = _make_prompt(identity_a)
        mock_repo.load.return_value = prompt
        service.mark_completed(prompt.id)
        mock_repo.update.assert_not_called()

    def test_mark_nonexistent_no_error(self, service, mock_repo):
        mock_repo.load.side_effect = KeyError("nope")
        service.mark_completed("bad-id")  # should not raise

    def test_mark_paused_noop(self, service, mock_repo, identity_a):
        prompt = _make_prompt(
            identity_a,
            status=ScheduleStatus.PAUSED,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
        )
        mock_repo.load.return_value = prompt
        service.mark_completed(prompt.id)
        mock_repo.update.assert_not_called()

    def test_mark_already_completed_noop(self, service, mock_repo, identity_a):
        prompt = _make_prompt(
            identity_a,
            status=ScheduleStatus.COMPLETED,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
        )
        mock_repo.load.return_value = prompt
        service.mark_completed(prompt.id)
        mock_repo.update.assert_not_called()


# ═══════════════════════════════════════════════════════════════════
# 3.9 Reconciliation (read-time Temporal → Mongo sync)
# ═══════════════════════════════════════════════════════════════════

class TestServiceReconciliation:
    """Tests for _reconcile_if_needed, exercised via get() and list_enriched()."""

    def test_get_reconciles_exhausted_schedule(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Finite schedule that Temporal reports as exhausted → COMPLETED."""
        from mas.scheduling.ports import ScheduleInfo

        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=3),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt
        mock_schedule_port.describe.return_value = ScheduleInfo(
            paused=False, remaining_actions=0, running=False,
        )

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.COMPLETED
        assert result.completed_at is not None
        mock_repo.update.assert_called_once()

    def test_get_no_reconcile_when_still_running(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Finite schedule still running in Temporal → stays ACTIVE."""
        from mas.scheduling.ports import ScheduleInfo

        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=3),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt
        mock_schedule_port.describe.return_value = ScheduleInfo(
            paused=False, remaining_actions=2, running=True,
        )

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_repo.update.assert_not_called()

    def test_get_reconciles_when_schedule_not_found(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Schedule deleted externally → mark COMPLETED."""
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            engine_handle="sched-gone",
        )
        mock_repo.load.return_value = prompt
        mock_schedule_port.describe.side_effect = EngineScheduleNotFoundError("sched-gone")

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.COMPLETED

    def test_get_skips_reconcile_on_describe_error(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Transient RPC error → leave ACTIVE, don't block the read."""
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt
        mock_schedule_port.describe.side_effect = RuntimeError("connection refused")

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_repo.update.assert_not_called()

    def test_get_skips_reconcile_for_infinite_schedule(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Unlimited schedule → no describe call at all."""
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1)),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_schedule_port.describe.assert_not_called()

    def test_get_skips_reconcile_for_paused_schedule(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Paused schedule → no describe call."""
        prompt = _make_prompt(
            identity_a,
            status=ScheduleStatus.PAUSED,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.PAUSED
        mock_schedule_port.describe.assert_not_called()

    def test_get_reconciles_with_noop_engine(
        self, mock_repo, mock_blueprint_service, identity_a,
    ):
        """NoOp engine reports schedule not found → marks finite schedule COMPLETED."""
        svc = WorkflowScheduleService(
            schedule_repo=mock_repo,
            schedule_engine=NoOpScheduleEngine(),
            blueprint_service=mock_blueprint_service,
        )
        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            engine_handle="sched-abc",
        )
        mock_repo.load.return_value = prompt

        result = svc.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.COMPLETED

    def test_list_enriched_reconciles_per_prompt(
        self, service, mock_repo, mock_schedule_port, mock_blueprint_service, identity_a,
    ):
        """list_enriched reconciles each finite prompt individually."""
        from mas.scheduling.ports import BatchDescribeResult, ScheduleInfo

        active_prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1), remaining_actions=1),
            engine_handle="sched-1",
        )
        infinite_prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(interval=timedelta(hours=1)),
            engine_handle="sched-2",
        )
        mock_repo.list_by_identity.return_value = [active_prompt, infinite_prompt]
        mock_schedule_port.describe_batch.return_value = BatchDescribeResult(
            found={"sched-1": ScheduleInfo(paused=False, remaining_actions=0, running=False)},
            errored=frozenset(),
        )

        result = service.list_enriched(identity=identity_a)
        assert result[0]["schedule_status"] == "completed"
        assert result[1]["schedule_status"] == "active"
        mock_schedule_port.describe_batch.assert_called_once_with(["sched-1"])

    def test_reconcile_with_end_at_schedule(
        self, service, mock_repo, mock_schedule_port, identity_a,
    ):
        """Schedule with end_at (no remaining_actions) is also reconciled."""
        from mas.scheduling.ports import ScheduleInfo

        prompt = _make_prompt(
            identity_a,
            schedule=ScheduleDefinition(
                interval=timedelta(hours=1),
                end_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            ),
            engine_handle="sched-end",
        )
        mock_repo.load.return_value = prompt
        mock_schedule_port.describe.return_value = ScheduleInfo(
            paused=False, remaining_actions=None, running=True,
        )

        result = service.get(prompt.id, identity=identity_a)
        assert result.schedule_status == ScheduleStatus.ACTIVE
        mock_schedule_port.describe.assert_called_once()
