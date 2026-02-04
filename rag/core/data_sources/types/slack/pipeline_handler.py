"""Slack Pipeline Handler - Source-specific pipeline operations for Slack."""
from typing import List, Dict, Any, Tuple

from core.pipeline.domain.port import SourcePipelinePort, PipelineContext
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import VectorChunk
from core.data_sources.types.slack.domain.processor import SlackProcessor
from infrastructure.sources.slack.connector import SlackConnector
from infrastructure.sources.slack.chunker import SlackChunkerStrategy
from shared.logger import logger

from global_utils.helpers.helpers import get_time_range_bounds_from_type_data


class SlackPipelineHandler(SourcePipelinePort):
    """
    Handler for Slack pipeline operations.
    
    Coordinates Slack-specific data flow through collection,
    processing, and embedding stages.
    
    This handler:
    - Collects messages and threads from Slack channels
    - Processes messages (normalizes text, handles mentions)
    - Chunks conversations and generates embeddings
    """
    
    def __init__(
        self,
        connector: SlackConnector,
        processor: SlackProcessor,
        chunker: SlackChunkerStrategy,
        embedder: EmbeddingGenerator,
    ):
        """
        Initialize the Slack pipeline handler.
        
        Args:
            connector: Slack connector for API communication
            processor: Slack processor for message transformation
            chunker: Slack chunker for conversation splitting
            embedder: Embedding generator for vector creation
        """
        self._connector = connector
        self._processor = processor
        self._chunker = chunker
        self._embedder = embedder
    
    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "SLACK"
    
    def collect(self, context: PipelineContext) -> Tuple[List[Dict], List[List[Dict]]]:
        """
        Collect Slack messages and threads.
        
        Args:
            context: Pipeline context with channel information
            
        Returns:
            Tuple of (main_messages, thread_messages)
        """
        type_data = context.metadata.get("type_data")
        oldest, latest = get_time_range_bounds_from_type_data(type_data, output="slack_ts")
        
        if oldest or latest:
            logger.info(
                f"Fetching messages for channel {context.source_name} "
                f"in range oldest={oldest}, latest={latest}"
            )
            return self._connector.get_conversations_history(
                channel_id=context.source_id,
                oldest=oldest,
                latest=latest,
            )
        
        logger.info(
            f"Fetching all messages for channel {context.source_name} "
            "(no time range specified)"
        )
        return self._connector.get_conversations_history(
            channel_id=context.source_id,
        )
    
    def process(
        self, 
        context: PipelineContext, 
        raw_data: Tuple[List[Dict], List[List[Dict]]]
    ) -> Tuple[List[Dict], List[List[Dict]]]:
        """
        Process messages and threads.
        
        Args:
            context: Pipeline context with channel information
            raw_data: Tuple of (main_messages, thread_messages) from collect
            
        Returns:
            Tuple of (processed_main, processed_threads)
        """
        messages, threads = raw_data
        
        processed_main = self._processor.process(
            messages, 
            channel_name=context.source_name
        )
        
        processed_threads = [
            self._processor.process(thread, channel_name=context.source_name)
            for thread in threads
        ]
        
        return processed_main, processed_threads
    
    def chunk_and_embed(
        self, 
        context: PipelineContext, 
        processed: Tuple[List[Dict], List[List[Dict]]]
    ) -> List[VectorChunk]:
        """
        Chunk content and generate embeddings.
        
        Args:
            context: Pipeline context
            processed: Tuple of (processed_main, processed_threads)
            
        Returns:
            List of VectorChunk objects ready for storage
        """
        main, threads = processed
        upload_by = context.metadata.get("upload_by", "default")
        
        # Chunk main messages
        chunks = self._chunker.chunk_content(main, upload_by=upload_by)
        
        # Chunk thread messages
        for thread in threads:
            chunks.extend(self._chunker.chunk_content(thread, upload_by=upload_by))
        
        # Enrich with source metadata
        for idx, chunk in enumerate(chunks):
            chunk.setdefault("metadata", {}).update({
                "source_id": context.source_id,
                "source_type": self.source_type,
                "chunk_index": idx,
            })
        
        # Generate embeddings and convert to domain objects
        enriched_dicts = self._embedder.generate_embeddings(chunks)
        
        return [
            VectorChunk(
                text=d["text"],
                embedding=d["embedding"].tolist() if hasattr(d["embedding"], 'tolist') else d["embedding"],
                metadata=d.get("metadata", {})
            )
            for d in enriched_dicts
        ]
    
    def get_summary(self, context: PipelineContext, collected: Any) -> Dict:
        """
        Get execution summary for Slack pipeline.
        
        Args:
            context: Pipeline context
            collected: Collected data (messages, threads)
            
        Returns:
            Summary dictionary with Slack-specific information
        """
        return {
            "is_private": context.metadata.get("is_private"),
        }
