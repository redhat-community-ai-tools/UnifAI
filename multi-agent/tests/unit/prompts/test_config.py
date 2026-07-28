"""Unit tests for Configuration and AppConfig extensions.

(Test Plan section 16.1)
"""
import pytest

from config.app_config import AppConfig


class TestAppConfigExtensions:
    def test_scheduled_prompts_coll_default(self):
        cfg = AppConfig.get_instance()
        assert cfg.scheduled_prompts_coll == "scheduled_prompts"

    def test_existing_config_unaffected(self):
        cfg = AppConfig.get_instance()
        assert cfg.engine_name == "temporal"
        assert cfg.temporal_task_queue == "graph-engine"
        assert cfg.mongo_db == "UnifAI"
