"""Unit tests for Configuration and AppConfig extensions.

(Test Plan section 16.1)
"""
import pytest

from config.app_config import AppConfig


class TestAppConfigExtensions:
    def test_workflow_schedules_coll_default(self):
        cfg = AppConfig.get_instance()
        assert cfg.workflow_schedules_coll == "workflow_schedules"

    def test_existing_config_unaffected(self):
        cfg = AppConfig.get_instance()
        assert cfg.engine_name == "temporal"
        assert cfg.temporal_task_queue == "graph-engine"
        assert cfg.mongo_db == "UnifAI"
