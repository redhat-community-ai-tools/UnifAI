"""
Data source types and validation models for the DataPipelineHub backend.

This module contains type definitions and validation models for different data sources:
- Metadata dataclasses for pipeline execution (SlackMetadata, DocumentMetadata)
- Pydantic models for type validation and MongoDB storage (SlackTypeData, DocumentTypeData)
- Type aliases for extensibility (SourceMetadata, SourceTypeData)

These models ensure type safety and data validation across the application.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, Union, List
from datetime import datetime
from pydantic import BaseModel, Field

@dataclass(frozen=True)
class SlackMetadata:
    """Metadata for Slack data sources used in pipeline execution."""
    channel_id: str
    channel_name: Optional[str] = None
    is_private: Optional[bool] = None
    upload_by: Optional[str] = None
    pipeline_id: Optional[str] = None
    type_data: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadata for Document data sources used in pipeline execution."""
    doc_id: str
    doc_name: Optional[str] = None
    doc_path: Optional[str] = None
    upload_by: Optional[str] = None
    pipeline_id: Optional[str] = None

class SlackTypeData(BaseModel):
    """
    Pydantic model for Slack source type data validation.
    
    This model validates the type_data field that gets stored in MongoDB
    for Slack data sources. It includes both source-specific fields and
    optional user-defined metadata from the frontend.
    """
    is_private: bool = Field(default=False, description="Whether the channel is private")
    
    # Optional user-defined metadata fields that can be added from frontend
    dateRange: Optional[str] = Field(default=None, description="User-defined date range settings (e.g., '7d', '30d')")
    start_timestamp: Optional[datetime] = Field(default=None, description="Start date for the range (datetime object)")
    end_timestamp: Optional[datetime] = Field(default=None, description="End date for the range (datetime object)")
    communityPrivacy: Optional[str] = Field(default=None, description="Community privacy settings")
    includeThreads: Optional[bool] = Field(default=None, description="Whether to include thread messages")
    
    class Config:
        extra = "allow"  # Allow additional fields for user-defined metadata


class DocumentTypeData(BaseModel):
    """
    Pydantic model for Document source type data validation.
    
    This model validates the type_data field that gets stored in MongoDB
    for Document data sources. It includes both source-specific fields and
    optional user-defined metadata from the frontend.
    """
    file_type: str = Field(..., description="File extension/type")
    doc_path: str = Field(..., description="Path to the document")
    page_count: int = Field(default=0, description="Number of pages in the document")
    full_text: str = Field(default="", description="Full text content")
    file_size: int = Field(default=0, description="File size in bytes")
    md5: Optional[str] = Field(default=None, description="MD5 checksum of the file for deduplication")
    
    # Optional user-defined metadata fields that can be added from frontend
    dateRange: Optional[Dict[str, Any]] = Field(default=None, description="User-defined date range settings")
    communityPrivacy: Optional[str] = Field(default=None, description="Community privacy settings")
    
    class Config:
        extra = "allow"  # Allow additional fields for user-defined metadata

class RegisteredSource(BaseModel):
    """
    Pydantic model for registered source data structure.
    
    This model represents a successfully registered data source that contains
    all the essential information needed for pipeline execution.
    """
    pipeline_id: str = Field(..., description="Unique pipeline identifier")
    metadata: Dict[str, Any] = Field(..., description="Serialized metadata object")
    source_type: str = Field(..., description="Type of data source (SLACK, DOCUMENT, etc.)")
    upload_by: str = Field(..., description="User who initiated the registration")
    type_data: Optional[Dict[str, Any]] = Field(default=None, description="Stored type_data for the source")


class RegistrationResponse(BaseModel):
    """
    Pydantic model for registration task response.
    
    This model represents containing the status and list of registered sources.
    """
    status: str = Field(..., description="Registration status")
    registered_sources: List[RegisteredSource] = Field(..., description="List of successfully registered sources")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="List of sources that failed registration with issue details")


class PipelineExecutionResult(BaseModel):
    """
    Pydantic model for pipeline execution task response.
    
    This model represents the response returned by the execute_pipeline_task
    containing the execution status and results.
    """
    pipeline_id: str = Field(..., description="Pipeline identifier that was executed")
    source_type: str = Field(..., description="Type of data source that was processed")
    status: str = Field(..., description="Execution status (success, error, etc.)")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Execution result data")

# Union type for all metadata types
SourceMetadata = Union[SlackMetadata, DocumentMetadata]

# Union type for all type data models  
SourceTypeData = Union[SlackTypeData, DocumentTypeData] 