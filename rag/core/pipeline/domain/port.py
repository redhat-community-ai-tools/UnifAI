"""Source Pipeline Port - Interface for source-specific pipeline operations."""
from abc import ABC, abstractmethod
from typing import Any, List, Dict
from dataclasses import dataclass

from core.vector.domain.model import VectorChunk


@dataclass(frozen=True)
class PipelineContext:
    """
    Immutable context for pipeline execution.
    
    Contains all the information needed to execute a pipeline
    for a specific source.
    """
    pipeline_id: str
    source_type: str
    source_id: str
    source_name: str
    metadata: Dict[str, Any]


class SourcePipelinePort(ABC):
    """
    Port defining source-specific pipeline operations.
    
    Each source type (Slack, Document, etc.) implements this interface
    to handle its specific data collection, processing, and embedding flow.
    
    The pipeline executor uses this port to orchestrate the pipeline
    without knowing the source-specific implementation details.
    """
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """
        Return the source type identifier.
        
        Returns:
            Source type string (e.g., 'SLACK', 'DOCUMENT')
        """
        ...
    
    @abstractmethod
    def collect(self, context: PipelineContext) -> Any:
        """
        Collect raw data from the source.
        
        Args:
            context: Pipeline execution context
            
        Returns:
            Raw data from the source (format depends on source type)
        """
        ...
    
    @abstractmethod
    def process(self, context: PipelineContext, raw_data: Any) -> Any:
        """
        Process collected data into a normalized format.
        
        Args:
            context: Pipeline execution context
            raw_data: Raw data from the collect step
            
        Returns:
            Processed data ready for chunking
        """
        ...
    
    @abstractmethod
    def chunk_and_embed(self, context: PipelineContext, processed: Any) -> List[VectorChunk]:
        """
        Chunk content and generate embeddings.
        
        Args:
            context: Pipeline execution context
            processed: Processed data from the process step
            
        Returns:
            List of VectorChunk objects ready for storage
        """
        ...
    
    @abstractmethod
    def get_summary(self, context: PipelineContext, collected: Any) -> Dict:
        """
        Get execution summary for reporting.
        
        Args:
            context: Pipeline execution context
            collected: Collected data (for extracting stats)
            
        Returns:
            Summary dictionary with source-specific information
        """
        ...
    
    def cleanup(self, context: PipelineContext) -> bool:
        """
        Optional cleanup hook.
        
        Override in handlers that require cleanup (e.g., deleting temp files).
        
        Args:
            context: Pipeline execution context
            
        Returns:
            True if cleanup was performed, False otherwise
        """
        return False

