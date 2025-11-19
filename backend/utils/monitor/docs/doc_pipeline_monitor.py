from typing import Dict, List
from shared.logger import logger
from ..pipeline_monitor_base import SourceType
from ..pipeline_monitor import PipelineMonitor

class DocPipelineMonitor:
    """
    Specialized monitor for Document pipelines.
    
    This class extends the base monitoring capabilities with Document-specific features.
    """
    
    def __init__(self, monitor: PipelineMonitor):
        """
        Initialize the Document pipeline monitor.
        
        Args:
            monitor: The base pipeline monitor instance
        """
        self.monitor = monitor
        logger.info("Initialized DocPipelineMonitor")
    
    # def get_doc_stats(self, doc_id: str) -> Dict:
    #     """
    #     Get statistics for a specific document.
        
    #     Args:
    #         doc_id: The ID of the document
            
    #     Returns:
    #         Dictionary containing document statistics
    #     """
    #     pipeline_id = f"doc_{doc_id}"
    #     logger.debug(f"Retrieving stats for document pipeline: {pipeline_id}")
    #     return self.monitor.get_pipeline_stats(pipeline_id)
    
    def get_all_docs_stats(self) -> Dict:
        """
        Get aggregated statistics for all Document pipelines.
        
        Returns:
            Dictionary containing aggregated Document statistics
        """
        logger.debug("Retrieving aggregated stats for all document pipelines")
        return self.monitor.get_source_stats(SourceType.DOCUMENT)
    
    # def get_active_docs(self) -> List[Dict]:
    #     """
    #     Get all active Document pipelines.
        
    #     Returns:
    #         List of active Document pipeline dictionaries
    #     """
    #     logger.debug("Retrieving active document pipelines")
    #     return self.monitor.get_active_pipelines(SourceType.DOCUMENT)
    
    def get_recent_docs_activity(self, limit: int = 10) -> List[str]:
        """
        Get recent log entries for Document pipelines.
        
        Args:
            limit: Maximum number of log entries to return
            
        Returns:
            List of log message strings
        """
        logger.debug(f"Retrieving recent document pipeline activity (limit: {limit})")
        return self.monitor.get_recent_activity(SourceType.DOCUMENT, limit)