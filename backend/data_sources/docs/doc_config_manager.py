
import os
from typing import List, Optional, Tuple
from utils.configuration_manager import ConfigurationManager

class DocConfigManager(ConfigurationManager):
    """
    Configuration manager for document processing.
    
    Manages settings for document parsing and extraction operations.
    """
    
    DEFAULT_CONFIG = {
        "extraction_mode": "default",
        "include_metadata": True,
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "supported_extensions": [".pdf", ".docx", ".md", ".pptx"],
        "max_file_size_mb": 50,
        "timeout_seconds": 300,
        # Note: The following parameters are kept for future use if docling adds these features
        # Currently docling.DocumentConverter.convert() doesn't support these parameters
        "use_ocr": False,  # Not currently supported by docling
        "ocr_language": "eng",  # Not currently supported by docling
        "extract_tables": True,  # Not currently supported by docling
        "extract_images": False,  # Not currently supported by docling
        "image_extraction_path": "./extracted_images/",
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the document configuration manager.
        
        Args:
            config_path: Optional path to a configuration file
        """
        super().__init__(config_path)
        
        # Set default configurations if not already set
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in self._config:
                self._config[key] = value
                
        # Create directory for image extraction if enabled
        if self._config.get("extract_images", False):
            os.makedirs(self._config.get("image_extraction_path", "./extracted_images/"), exist_ok=True)
    
    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        Validate the current configuration for document processing.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Validate supported extensions
        supported_extensions = self._config.get("supported_extensions", [])
        if not isinstance(supported_extensions, list) or not supported_extensions:
            errors.append("Supported extensions must be a non-empty list")
            
        # Validate numeric parameters
        numeric_params = {
            "chunk_size": (100, 10000),
            "chunk_overlap": (0, 5000),
            "max_file_size_mb": (1, 1000),
            "timeout_seconds": (30, 3600)
        }
        
        for param, (min_val, max_val) in numeric_params.items():
            value = self._config.get(param)
            if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                errors.append(f"{param} must be a number between {min_val} and {max_val}")
        
        # Validate boolean parameters
        bool_params = ["include_metadata", "use_ocr", "extract_tables", "extract_images"]
        for param in bool_params:
            if not isinstance(self._config.get(param), bool):
                errors.append(f"{param} must be a boolean value")
        
        # Validate path parameters
        if self._config.get("extract_images"):
            image_path = self._config.get("image_extraction_path")
            if not image_path or not isinstance(image_path, str):
                errors.append("image_extraction_path must be a valid directory path when extract_images is enabled")
        
        return len(errors) == 0, errors
    
    def get_supported_file_types(self) -> List[str]:
        """
        Get the list of supported file types.
        
        Returns:
            List of supported file extensions
        """
        return self.get_config_value("supported_extensions", [])
    
    def is_file_type_supported(self, file_extension: str) -> bool:
        """
        Check if a file type is supported.
        
        Args:
            file_extension: The file extension to check (without dot)
            
        Returns:
            True if supported, False otherwise
        """
        file_extension = file_extension.lower().lstrip('.')
        return file_extension in self.get_supported_file_types()