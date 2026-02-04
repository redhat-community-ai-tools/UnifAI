from abc import ABC, abstractmethod
from typing import Dict, List, Any, Union

class DataProcessor(ABC):
    """
    Abstract base class for all data processors in the pipeline.
    
    This class defines the common interface and shared functionality
    for processing different data sources (Jira, Slack, Documents).
    """
    
    def __init__(self):
        """Initialize the base data processor."""
        self._data = []
        self._processed_data = []
        
    @property
    def data_length(self) -> int:
        """Return the count of raw data items."""
        return len(self._data)
    
    @property
    def processed_data_length(self) -> int:
        """Return the count of processed data items."""
        return len(self._processed_data)
    
    @abstractmethod
    def process(self, data: Union[List[Dict[str, Any]], Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """
        Process the raw data from the source.
        
        Args:
            data: List of raw data items to process
            **kwargs: Additional parameters specific to the processor
            
        Returns:
            List of processed data items
        """
        pass
    
    @abstractmethod
    def clean_content(self, content: str) -> str:
        """
        Clean and normalize content text.
        
        Args:
            content: Raw content text
            
        Returns:
            Cleaned and normalized text
        """
        pass
    
    def get_processed_data(self) -> List[Dict[str, Any]]:
        """Return the processed datsa."""
        return self._processed_data

