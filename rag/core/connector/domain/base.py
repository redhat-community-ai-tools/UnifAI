"""Base data connector - domain port."""
from abc import ABC, abstractmethod
from typing import List, Any


class DataConnector(ABC):
    """
    Abstract base class for data collection components.
    
    Provides a common interface for retrieving data from various sources.
    """
    
    def __init__(self, config_manager: Any):
        """
        Initialize the data connector.
        
        Args:
            config_manager: Configuration manager for this connector
        """
        self._config_manager = config_manager
        self._base_url: str = ""
        self._available_apis: List[str] = []
    
    @property
    def base_url(self) -> str:
        """Get the base URL for API calls."""
        return self._base_url
    
    @base_url.setter
    def base_url(self, url: str) -> None:
        """Set the base URL for API calls."""
        self._base_url = url
    
    @property
    def available_apis(self) -> List[str]:
        """Get the list of available API endpoints."""
        return self._available_apis
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the data source.
        
        Returns:
            True if authentication was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to the data source.
        
        Returns:
            True if connection is successful, False otherwise
        """
        pass

