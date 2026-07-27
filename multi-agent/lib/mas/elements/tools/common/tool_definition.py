"""
Provider-agnostic tool schema — pure data, no execution logic.

This is the universal intermediate representation between the domain layer
(tools that execute) and the LLM layer (tools the model sees for function-calling).

Usage:
    definition = ToolDefinition(name="search", description="Search docs", parameters={...})
    bound_llm = llm.bind_tools([definition])
"""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field

_EMPTY_PARAMS: Dict[str, Any] = {"type": "object", "properties": {}}


class ToolDefinition(BaseModel):
    """Provider-agnostic tool schema for LLM function-calling registration.

    Carries only the metadata an LLM needs to generate tool calls:
    name, description, and a JSON Schema of the parameters.

    Immutable (frozen) to prevent accidental mutation after binding.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=lambda: dict(_EMPTY_PARAMS))
