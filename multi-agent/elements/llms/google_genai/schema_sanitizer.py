"""
Schema sanitizer for Google GenAI compatibility.

Google GenAI has strict JSON Schema validation that rejects certain
property patterns that other LLM providers accept. This module provides
sanitization utilities specific to Google GenAI's requirements.
"""

from typing import Any, Dict, Set


class SchemaSanitizer:
    """
    Sanitizes JSON schemas for Google GenAI consumption.
    
    Removes known invalid property patterns that cause validation errors
    with Google GenAI's strict schema validation.
    """

    @staticmethod
    def is_invalid_property(prop_value: Any) -> bool:
        """
        Check if a property value is a known invalid pattern.
        
        Known invalid patterns:
        - None
        - Empty dict {}
        - Dict with only 'title' key (e.g., {'title': 'Service Name'})
        
        These typically represent internal service dependencies from MCP
        servers that shouldn't be exposed to the LLM.
        """
        if prop_value is None:
            return True
        if not isinstance(prop_value, dict):
            return False
        if not prop_value:
            return True
        if prop_value.keys() == {'title'}:
            return True
        return False

    @classmethod
    def sanitize(cls, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize a JSON schema by removing known invalid properties.
        
        Args:
            schema: The JSON schema to sanitize.
            
        Returns:
            A new sanitized schema dictionary.
        """
        if not schema or not isinstance(schema, dict):
            return schema or {}

        result = {}
        valid_property_names: Set[str] = set()

        for key, value in schema.items():
            if key == "properties" and isinstance(value, dict):
                result[key], valid_property_names = cls._sanitize_properties(value)
            elif key == "required":
                continue  # Handle after properties are processed
            elif isinstance(value, dict):
                result[key] = cls.sanitize(value)
            else:
                result[key] = value

        # Filter required array to only include valid properties
        if "required" in schema and isinstance(schema["required"], list):
            filtered = [r for r in schema["required"] if r in valid_property_names]
            if filtered:
                result["required"] = filtered

        return result

    @classmethod
    def _sanitize_properties(cls, properties: Dict[str, Any]) -> tuple[Dict[str, Any], Set[str]]:
        """
        Sanitize a properties dictionary.
        
        Returns:
            Tuple of (sanitized properties dict, set of valid property names).
        """
        sanitized = {}
        valid_names = set()

        for name, value in properties.items():
            if cls.is_invalid_property(value):
                continue
            sanitized[name] = cls.sanitize(value) if isinstance(value, dict) else value
            valid_names.add(name)

        return sanitized, valid_names
