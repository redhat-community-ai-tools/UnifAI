"""Unit tests for Identity, Ownership, and Security concerns.

Covers: Personal mode isolation, team mode sharing, cross-identity blocking,
        authorization on all operations, injection safety.
(Test Plan sections 7, 19)
"""
from datetime import timedelta, timezone, datetime
from unittest.mock import Mock

import pytest

from mas.core.identity import Identity
from mas.scheduling.models import (
    ScheduleDefinition,
    ScheduleStatus,
    WorkflowSchedule,
)
from mas.scheduling.service import (
    ScheduleNotFoundError,
    SchedulePermissionError,
    WorkflowScheduleService,
)


def _make_prompt(identity, **kwargs):
    return WorkflowSchedule(
        blueprint_id=kwargs.pop("blueprint_id", "bp-1"),
        identity=identity,
        text=kwargs.pop("text", "test"),
        schedule=ScheduleDefinition(interval=timedelta(minutes=15)),
        schedule_status=kwargs.pop("status", ScheduleStatus.ACTIVE),
        engine_handle=kwargs.pop("engine_handle", "sched-1"),
        **kwargs,
    )


@pytest.fixture
def user_a():
    return Identity.user("user-a")


@pytest.fixture
def user_b():
    return Identity.user("user-b")


@pytest.fixture
def team_x():
    return Identity.team("team-x")


@pytest.fixture
def team_y():
    return Identity.team("team-y")


@pytest.fixture
def service():
    repo = Mock()
    repo.count_active_by_blueprint.return_value = 0
    repo.save.return_value = "id"
    repo.update.return_value = True
    repo.delete.return_value = True

    bp_svc = Mock()
    bp_svc.exists.return_value = True

    port = Mock()
    port.create_schedule.return_value = "sched-id"

    svc = WorkflowScheduleService(
        schedule_repo=repo,
        schedule_engine=port,
        blueprint_service=bp_svc,
    )
    return svc


# ═══════════════════════════════════════════════════════════════════
# 7.1 Personal Mode
# ═══════════════════════════════════════════════════════════════════

class TestPersonalMode:
    def test_user_only_sees_own_prompts(self, service, user_a, user_b):
        prompts_a = [_make_prompt(user_a) for _ in range(3)]
        service._repo.list_by_identity.return_value = prompts_a
        result = service.list(identity=user_a)
        assert len(result) == 3
        service._repo.list_by_identity.assert_called_with(user_a)

    def test_user_cannot_manage_others_prompt(self, service, user_a, user_b):
        prompt = _make_prompt(user_a)
        service._repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.pause(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.resume(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.delete(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.trigger(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.update(prompt.id, identity=user_b, text="hack")


# ═══════════════════════════════════════════════════════════════════
# 7.2 Team Mode
# ═══════════════════════════════════════════════════════════════════

class TestTeamMode:
    def test_team_members_see_team_prompts(self, service, team_x):
        prompts = [_make_prompt(team_x) for _ in range(2)]
        service._repo.list_by_identity.return_value = prompts
        result = service.list(identity=team_x)
        assert len(result) == 2

    def test_team_member_can_manage_team_prompt(self, service, team_x):
        prompt = _make_prompt(team_x)
        service._repo.load.return_value = prompt
        result = service.pause(prompt.id, identity=team_x)
        assert result.schedule_status == ScheduleStatus.PAUSED

    def test_other_team_cannot_access(self, service, team_x, team_y):
        prompt = _make_prompt(team_x)
        service._repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.get(prompt.id, identity=team_y)


# ═══════════════════════════════════════════════════════════════════
# 7.3 Cross-Context Isolation
# ═══════════════════════════════════════════════════════════════════

class TestCrossContextIsolation:
    def test_personal_not_visible_in_team(self, service, user_a, team_x):
        personal_prompt = _make_prompt(user_a)
        service._repo.load.return_value = personal_prompt
        with pytest.raises(SchedulePermissionError):
            service.get(personal_prompt.id, identity=team_x)

    def test_team_not_visible_in_personal(self, service, user_a, team_x):
        team_prompt = _make_prompt(team_x)
        service._repo.load.return_value = team_prompt
        with pytest.raises(SchedulePermissionError):
            service.get(team_prompt.id, identity=user_a)


# ═══════════════════════════════════════════════════════════════════
# 19. Security & Authorization
# ═══════════════════════════════════════════════════════════════════

class TestSecurity:
    def test_cross_identity_access_blocked_all_operations(self, service, user_a, user_b):
        prompt = _make_prompt(user_a)
        service._repo.load.return_value = prompt

        with pytest.raises(SchedulePermissionError):
            service.get(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.update(prompt.id, identity=user_b, text="x")
        with pytest.raises(SchedulePermissionError):
            service.pause(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.resume(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.delete(prompt.id, identity=user_b)
        with pytest.raises(SchedulePermissionError):
            service.trigger(prompt.id, identity=user_b)

    def test_get_runs_respects_ownership(self, service, user_a, user_b):
        prompt = _make_prompt(user_a)
        service._repo.load.return_value = prompt
        with pytest.raises(SchedulePermissionError):
            service.get_runs(prompt.id, identity=user_b)

    def test_nosql_injection_in_text_stored_literally(self, service, user_a):
        """Verify that injection-like text is treated as plain string."""
        malicious = "'; db.dropDatabase(); //"
        result = service.create(
            identity=user_a,
            blueprint_id="bp-1",
            text=malicious,
            schedule={"interval": "PT60S"},
        )
        assert result.text == malicious

    def test_list_enriched_blueprint_filter_bypasses_identity(self, service, user_a):
        """When blueprint_id is provided, list_enriched uses find_by_blueprint (no identity filter)."""
        service._repo.find_by_blueprint.return_value = []
        service.list_enriched(identity=user_a, blueprint_id="bp-x")
        service._repo.find_by_blueprint.assert_called_once_with("bp-x")
        service._repo.list_by_identity.assert_not_called()
