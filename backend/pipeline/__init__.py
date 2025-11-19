"""
Pipeline module initialization.

This module imports all pipeline factory subclasses and pipeline subclasses 
to ensure they are automatically registered in their respective registries 
when the pipeline module is imported. This prevents bugs where subclasses 
aren't registered because they weren't imported elsewhere.
"""

from .pipeline_factory import PipelineFactory
from .doc_pipeline_factory import DocumentPipelineFactory
from .slack_pipeline_factory import SlackPipelineFactory

from .pipeline import Pipeline
from .slack_pipeline import SlackPipeline
from .docs_pipeline import DocumentPipeline

__all__ = [
    "PipelineFactory",
    "DocumentPipelineFactory", 
    "SlackPipelineFactory",
    "Pipeline",
    "SlackPipeline",
    "DocumentPipeline"
] 