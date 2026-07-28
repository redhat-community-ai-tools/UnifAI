"""Regression tests for existing functionality unaffected by Scheduled Prompts.

Covers: PromptShortcutItem still works, SessionMeta backward compat,
        container bootstrap wiring, worker registration.
(Test Plan sections 14.1–14.8, automated portions)
"""
from datetime import timedelta

import pytest
from pydantic import ValidationError

from mas.core.identity import Identity
from mas.core.prompt import BasePrompt
from mas.blueprints.models.prompt_shortcuts import PromptShortcutItem, PromptShortcuts
from mas.session.domain.models import SessionMeta


# ═══════════════════════════════════════════════════════════════════
# 14.1 Manual Session (SessionMeta backward compat)
# ═══════════════════════════════════════════════════════════════════

class TestSessionMetaBackwardCompat:
    def test_source_field_optional(self):
        meta = SessionMeta()
        assert meta.source is None

    def test_legacy_sessions_without_source(self):
        """Old sessions without source/schedule_id load correctly."""
        meta = SessionMeta(title="old session")
        assert meta.source is None
        assert meta.schedule_id is None
        assert meta.prompt_text is None

    def test_source_schedule_fields_stored(self):
        meta = SessionMeta(source="schedule", schedule_id="p1", prompt_text="Run analysis")
        assert meta.source == "schedule"
        assert meta.schedule_id == "p1"
        assert meta.prompt_text == "Run analysis"

    def test_extra_allow_still_works(self):
        """Extra fields pass through (extra='allow')."""
        meta = SessionMeta(title="test", custom_field="custom_value")
        assert meta.model_extra["custom_field"] == "custom_value"


# ═══════════════════════════════════════════════════════════════════
# 14.2 PromptShortcutItem (No Regression)
# ═══════════════════════════════════════════════════════════════════

class TestPromptShortcutNoRegression:
    def test_still_inherits_base_prompt(self):
        assert issubclass(PromptShortcutItem, BasePrompt)

    def test_shortcuts_still_load(self):
        shortcuts = PromptShortcuts.parse([{"text": "hello"}])
        assert shortcuts.root[0].text == "hello"
        assert len(shortcuts.root[0].id) == 8

    def test_frozen_model_prevents_mutation(self):
        item = PromptShortcuts.parse([{"text": "x"}]).root[0]
        with pytest.raises(ValidationError):
            item.text = "new"

    def test_max_3_limit_unchanged(self):
        from mas.blueprints.exceptions import PromptShortcutsValidationError
        items = [{"text": f"p{i}", "id": f"{i:08x}"} for i in range(4)]
        with pytest.raises(PromptShortcutsValidationError):
            PromptShortcuts.parse(items)

    def test_serialization_unchanged(self):
        shortcuts = PromptShortcuts.parse([{"text": "hi", "id": "abcd1234"}])
        storage = shortcuts.to_storage()
        assert storage == [{"id": "abcd1234", "text": "hi"}]


# ═══════════════════════════════════════════════════════════════════
# 14.7 Temporal Worker (Registration)
# ═══════════════════════════════════════════════════════════════════

class TestWorkerRegistration:
    def test_scheduled_session_workflow_importable(self):
        from inbound.temporal.workflows.scheduled_session_workflow import ScheduledSessionWorkflow
        assert hasattr(ScheduledSessionWorkflow, "run")

    def test_schedule_activities_importable(self):
        from inbound.temporal.activities.schedule_activities import ScheduleActivities
        assert hasattr(ScheduleActivities, "create_scheduled_session")
        assert hasattr(ScheduleActivities, "stage_scheduled_inputs")
        assert hasattr(ScheduleActivities, "build_session_workflow_params")
        assert hasattr(ScheduleActivities, "post_execution")


# ═══════════════════════════════════════════════════════════════════
# 14.8 Container Bootstrap (Service wiring)
# ═══════════════════════════════════════════════════════════════════

class TestServiceWiring:
    def test_prompt_service_instantiation(self):
        """PromptService can be instantiated with minimal dependencies."""
        from unittest.mock import Mock
        from mas.prompts.service import PromptService
        svc = PromptService(
            prompt_repo=Mock(),
            schedule_port=None,
            blueprint_service=Mock(),
        )
        assert svc is not None

    def test_prompt_service_with_no_schedule_port(self):
        """PromptService works with schedule_port=None (non-temporal engine)."""
        from unittest.mock import Mock
        from mas.prompts.service import PromptService
        repo = Mock()
        repo.count_active_by_blueprint.return_value = 0
        repo.save.return_value = "id"
        repo.update.return_value = True

        identity = Identity.user("u1")

        bp_svc = Mock()
        bp_svc.exists.return_value = True
        doc = Mock()
        doc.spec_dict = {"name": "BP"}
        doc.identity = identity
        bp_svc.get_blueprint_draft_doc.return_value = doc

        svc = PromptService(prompt_repo=repo, schedule_port=None, blueprint_service=bp_svc)
        result = svc.create(
            identity=identity,
            blueprint_id="bp-1",
            text="hello",
            schedule={"interval": "PT60S"},
        )
        assert result.temporal_schedule_id is None


# ═══════════════════════════════════════════════════════════════════
# 16.1 AppConfig
# ═══════════════════════════════════════════════════════════════════

class TestAppConfigRegression:
    def test_existing_config_fields_present(self):
        from config.app_config import AppConfig
        cfg = AppConfig.get_instance()
        assert hasattr(cfg, "mongo_db")
        assert hasattr(cfg, "blueprint_coll")
        assert hasattr(cfg, "session_coll")
        assert hasattr(cfg, "engine_name")
        assert hasattr(cfg, "temporal_task_queue")
