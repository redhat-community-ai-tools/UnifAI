from enum import Enum

class Database(Enum):
    """Database names"""
    DATA_SOURCES = "data_sources"
    PIPELINE = "pipeline_monitoring"

class Collection(Enum):
    """Collection names"""
    SOURCES = "sources"
    CHUNKS = "chunks"
    SLACK_CHANNELS = "slack_channels"
    PIPELINES = "pipelines"

class DataSource(Enum):
    """Data source types with consistent naming"""
    SLACK = "slack"
    JIRA = "jira"
    DOCUMENT = "document"
    OTHER = "other"
    
    @property
    def upper_name(self) -> str:
        """Get uppercase name for legacy compatibility"""
        return self.value.upper()
    
class PipelineStatus(Enum):
    """Enum representing possible pipeline statuses."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    DONE = "DONE"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    CHUNKING_AND_EMBEDDING = "CHUNKING_AND_EMBEDDING"
    STORING = "STORING"
    COLLECTING = "COLLECTING"
    PROCESSING = "PROCESSING"
    ORCHESTRATING = "ORCHESTRATING"

class ActivePipelineStatus(Enum):
    """Enum representing active pipeline statuses."""
    PENDING = PipelineStatus.PENDING.value
    ACTIVE = PipelineStatus.ACTIVE.value
    COLLECTING = PipelineStatus.COLLECTING.value
    PROCESSING = PipelineStatus.PROCESSING.value
    CHUNKING_AND_EMBEDDING = PipelineStatus.CHUNKING_AND_EMBEDDING.value
    STORING = PipelineStatus.STORING.value
    ORCHESTRATING = PipelineStatus.ORCHESTRATING.value

    @classmethod
    def values(cls) -> list[str]:
        """Get all active status values as a list."""
        return [status.value for status in cls]
    
class SourceType(Enum):
    """Enum representing different data source types."""
    SLACK = DataSource.SLACK.upper_name
    JIRA = DataSource.JIRA.upper_name
    DOCUMENT = DataSource.DOCUMENT.upper_name
    OTHER = DataSource.OTHER.upper_name