import asyncio
from typing import Any, Dict, Optional, Type

from abc import ABC, abstractmethod
from pydantic import BaseModel

from .tool_definition import ToolDefinition

_EMPTY_PARAMS: Dict[str, Any] = {"type": "object", "properties": {}}


class BaseTool(ABC):
    """Abstract base class for all executable tools.

    Subclass this and implement ``run()`` (and optionally ``arun()``).
    Provide ``name``, ``description``, and an optional Pydantic
    ``args_schema`` whose JSON Schema is used by LLM providers
    for function-calling.
    """

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronous execution logic. Must be implemented by subclass."""
        raise NotImplementedError("run must be implemented by subclasses")

    async def arun(self, *args: Any, **kwargs: Any) -> Any:
        """Default async wrapper — runs sync method in thread pool."""
        return await asyncio.to_thread(self.run, *args, **kwargs)

    def get_args_schema_json(self) -> Optional[Dict[str, Any]]:
        """Return the JSON Schema dict for this tool's parameters."""
        if self.args_schema is None:
            return None
        if isinstance(self.args_schema, dict):
            return self.args_schema
        return self.args_schema.model_json_schema()

    def to_definition(self) -> ToolDefinition:
        """Extract a provider-agnostic ToolDefinition (schema only, no execution)."""
        return ToolDefinition(
            name=self.name,
            description=self.description or "",
            parameters=self.get_args_schema_json() or _EMPTY_PARAMS,
        )
