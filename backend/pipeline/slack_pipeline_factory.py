from functools import cached_property
from typing import Dict
from pipeline.pipeline_factory import PipelineFactory
from data_sources.slack.slack_config_manager import SlackConfigManager
from data_sources.slack.slack_connector import SlackConnector
from data_sources.slack.slack_data_processor import SlackProcessor
from data_sources.slack.slack_chunker_strategy import SlackChunkerStrategy
from shared.config import ChunkerConfig
from config.constants import DataSource
from config.app_config import AppConfig

class SlackPipelineFactory(PipelineFactory):
    SOURCE_TYPE = DataSource.SLACK.upper_name
    
    def __init__(
        self,
    ):
        super().__init__()
        self.app_config = AppConfig.get_instance()

    def _get_configured_connector(self) -> SlackConnector:
        config_manager = SlackConfigManager()
        config_manager.set_project_tokens(
            project_id="example-project",
            bot_token=self.app_config.default_slack_bot_token,
            user_token=self.app_config.default_slack_user_token
        )
        config_manager.set_default_project("example-project")
        return SlackConnector(config_manager) 
    
    def _create_collector(self) -> SlackConnector:
        connector = self._get_configured_connector()
        if not connector.authenticate():
            raise RuntimeError("Slack authentication failed")
        return connector
    
    def _create_processor(self) -> SlackProcessor:
        return SlackProcessor()
    
    def _create_chunker(self) -> SlackChunkerStrategy:
        cfg = ChunkerConfig()
        return SlackChunkerStrategy(
            max_tokens_per_chunk=cfg.max_tokens_per_chunk,
            overlap_tokens=cfg.overlap_tokens,
            time_window_seconds=300
        )
