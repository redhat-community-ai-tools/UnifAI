"""
Base prompt model — shared foundation for all prompt-like entities.

Lives in core/ so both `blueprints.models.prompt_shortcuts.PromptShortcutItem`
and `prompts.models.ScheduledPrompt` can inherit without circular deps.
"""
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class BasePrompt(BaseModel):
    """Shared foundation for all prompt-like entities."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Prompt text must not be empty")
        return stripped
