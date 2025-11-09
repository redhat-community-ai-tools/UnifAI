# pipelines/slack_pipeline.py

from typing import List, Dict, Tuple, Optional
from data_sources.slack.slack_data_processor import SlackProcessor
from data_sources.slack.slack_connector import SlackConnector
from data_sources.slack.slack_chunker_strategy import SlackChunkerStrategy
from shared.source_types import SlackMetadata
from config.constants import DataSource
from pipeline.pipeline import Pipeline
from utils.embedding.embedding_generator import EmbeddingGenerator
from utils.monitor.pipeline_monitor import PipelineMonitor
from utils.storage.vector_storage import VectorStorage
from shared.logger import logger
from datetime import datetime
from global_utils.helpers.helpers import get_time_range_bounds_from_type_data


class SlackPipeline(Pipeline):
    SOURCE_TYPE = DataSource.SLACK.upper_name
    def __init__(
        self,
        collector: SlackConnector,
        processor: SlackProcessor,
        chunker: SlackChunkerStrategy,
        embedder: EmbeddingGenerator,
        storage: VectorStorage,
        metadata: SlackMetadata,
        monitor: PipelineMonitor,
    ):
        self.collector = collector
        self.slack_processor = processor
        self.slack_chunker = chunker
        self.embedder = embedder
        self.metadata = metadata
        
        super().__init__(
            collector=collector,
            processor=processor,
            chunker=chunker,
            embedder=embedder,
            storage=storage,
            monitor=monitor,
            metadata=metadata
        )

    def get_source_id(self) -> str:
        return self.metadata.channel_id

    def get_source_name(self) -> str:
        return self.metadata.channel_name
        
    def summary(self) -> Dict:
        return {
            "is_private": self.metadata.is_private,
        }
        
    def collect_data(self) -> Tuple[List[Dict], List[List[Dict]]]:
        type_data = getattr(self.metadata, "type_data", None)
        oldest, latest = get_time_range_bounds_from_type_data(
            type_data,
            output="slack_ts",
        )
        if oldest or latest:
            logger.info(
                f"Fetching messages for channel {self.metadata.channel_name} in range oldest={oldest}, latest={latest}"
            )
            return self.collector.get_conversations_history(
                channel_id=self.metadata.channel_id,
                oldest=oldest,
                latest=latest,
            )
        logger.info(
            f"Fetching all messages for channel {self.metadata.channel_name} (no time range specified)"
        )
        return self.collector.get_conversations_history(
            channel_id=self.metadata.channel_id
        )

    def process_data(
        self, data: Tuple[List[Dict], List[List[Dict]]]
    ) -> Tuple[List[Dict], List[List[Dict]]]:
        messages, threads = data
        main = self.slack_processor.process(
            messages, channel_name=self.metadata.channel_name
        )
        thrs = [
            self.slack_processor.process(t, channel_name=self.metadata.channel_name)
            for t in threads
        ]
        return main, thrs

    def chunk_and_embed(
        self, processed: Tuple[List[Dict], List[List[Dict]]]
    ) -> List[Dict]:
        main, threads = processed
        upload_by = self.metadata.upload_by or "default"
        chunks = self.slack_chunker.chunk_content(main, upload_by=upload_by)
        for t in threads:
            chunks.extend(self.slack_chunker.chunk_content(t, upload_by=upload_by))

        for idx, c in enumerate(chunks):
            md = c.setdefault("metadata", {})
            md.update({
                "source_id": self.metadata.channel_id,
                "chunk_index": idx,
                "source_type": DataSource.SLACK.upper_name,
            })

        return self.embedder.generate_embeddings(chunks)
