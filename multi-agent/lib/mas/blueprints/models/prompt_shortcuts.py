from typing import List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


MAX_MANUAL_PROMPTS = 3


def _short_id() -> str:
    return uuid4().hex[:8]


class PromptShortcutItem(BaseModel):
    """
    A single prompt shortcut entry.

    - `id`:    Stable 8-char hex identifier (auto-assigned if omitted).
    - `kind`:  Discriminator — "manual" now, "scheduled" in a future phase.
    - `text`:  The full prompt text inserted into the textarea on click.
               No character limit.
    """
    id: str = Field(default_factory=_short_id)
    kind: Literal["manual"] = "manual"
    text: str

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Prompt text must not be empty")
        return stripped


class PromptShortcuts(BaseModel):
    """
    Value object: the set of prompt shortcuts configured on a blueprint.

    Immutable after construction — create a new instance to modify.
    """
    prompts: List[PromptShortcutItem] = Field(default_factory=list)

    @field_validator("prompts")
    @classmethod
    def validate_prompts(cls, v: List[PromptShortcutItem]) -> List[PromptShortcutItem]:
        manual = [p for p in v if p.kind == "manual"]
        if len(manual) > MAX_MANUAL_PROMPTS:
            raise ValueError(f"At most {MAX_MANUAL_PROMPTS} manual prompt shortcuts allowed")
        return v

    # ── Factories ──

    @classmethod
    def from_spec(cls, spec_dict: dict) -> "PromptShortcuts":
        """
        Extract from a raw spec_dict. Never raises.

        Legacy blueprints have no ``prompt_shortcuts`` key at all — returns empty.
        Current format: List[dict] with {id?, kind?, text}.
        """
        raw = spec_dict.get("prompt_shortcuts")
        if not raw or not isinstance(raw, list):
            return cls(prompts=[])
        try:
            items = [
                PromptShortcutItem(**entry)
                for entry in raw
                if isinstance(entry, dict) and "text" in entry
            ]
            return cls(prompts=items)
        except (ValueError, TypeError):
            return cls(prompts=[])

    @classmethod
    def from_raw_list(cls, raw: Optional[list]) -> "PromptShortcuts":
        """Construct from a raw list (as returned by the repository)."""
        if not raw or not isinstance(raw, list):
            return cls(prompts=[])
        return cls.from_spec({"prompt_shortcuts": raw})

    # ── Serialization ──

    def to_storage(self) -> Optional[List[dict]]:
        """
        Serialize for persistence.
        Returns None when empty — signals the repo to $unset the key.
        """
        if not self.prompts:
            return None
        return [
            {"id": item.id, "kind": item.kind, "text": item.text}
            for item in self.prompts
        ]

    # ── Queries ──

    @property
    def is_empty(self) -> bool:
        return len(self.prompts) == 0

    @property
    def is_full(self) -> bool:
        manual = [p for p in self.prompts if p.kind == "manual"]
        return len(manual) >= MAX_MANUAL_PROMPTS

    @property
    def count(self) -> int:
        return len(self.prompts)
