"""Base configuration manager - infrastructure adapter."""
import os
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from shared.logger import logger


class BaseConfigurationManager(ABC):
    """
    Base configuration manager with file loading capability.
    
    Provides common configuration management functionality including:
    - JSON config file loading/saving
    - Secrets management
    - Key-value config storage
    
    Matches backend's ConfigurationManager behavior for consistency.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Optional path to a configuration file
        """
        self._config: Dict[str, Any] = {}
        self._secrets: Dict[str, Any] = {}
        
        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
    
    def load_config(self, config_path: str) -> None:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
        """
        logger.info(f"Loading configuration from {config_path}")
        try:
            with open(config_path, 'r') as f:
                loaded_config = json.load(f)
                self._config.update(loaded_config.get('config', {}))
                self._secrets.update(loaded_config.get('secrets', {}))
        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {str(e)}")
            raise
    
    def save_config(self, config_path: str) -> None:
        """
        Save configuration to a JSON file.
        
        Args:
            config_path: Path to save the configuration
        """
        try:
            with open(config_path, 'w') as f:
                json.dump({
                    'config': self._config,
                    'secrets': self._secrets
                }, f, indent=2)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {config_path}: {str(e)}")
            raise
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: The configuration key
            default: Default value if key doesn't exist
            
        Returns:
            The configuration value or default
        """
        return self._config.get(key, default)
    
    def set_config_value(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: The configuration key
            value: The value to set
        """
        self._config[key] = value
    
    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get a secret value.
        
        Args:
            key: The secret key
            default: Default value if key doesn't exist
            
        Returns:
            The secret value or default
        """
        return self._secrets.get(key, default)
    
    def set_secret(self, key: str, value: Any) -> None:
        """
        Set a secret value.
        
        Args:
            key: The secret key
            value: The value to set
        """
        self._secrets[key] = value
    
    @abstractmethod
    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        Validate the current configuration.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        pass


