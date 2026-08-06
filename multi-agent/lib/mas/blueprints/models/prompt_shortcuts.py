from typing import ClassVar, List, Optional
from uuid import uuid4

import re

from pydantic import (
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationError,
    field_validator,
    model_serializer,
    model_validator,
)

from mas.core.prompt import BasePrompt
from mas.blueprints.exceptions import PromptShortcutsValidationError

MAX_PROMPT_SHORTCUTS = 3


def format_validation_errors(exc: ValidationError) -> str:
    """Format Pydantic validation errors into user-facing messages."""
    parts: list[str] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        path = ".".join(str(segment) for segment in loc if segment != "__root__")
        if not path and loc == ("__root__",):
            path = "prompt_shortcuts"
        msg = err.get("msg", "Invalid value")
        parts.append(f"{path}: {msg}" if path else str(msg))
    return "; ".join(parts) if parts else str(exc)


def _short_id() -> str:
    return uuid4().hex[:8]


class PromptShortcutItem(BasePrompt):
    """
    A single manual prompt shortcut on a blueprint.

    - `id`:   Stable 8-char hex identifier (auto-assigned if omitted).
    - `text`: The full prompt text inserted into the textarea on click.
              No character limit.  Inherited from BasePrompt.
    """
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=_short_id)

    _HEX8_RE: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9a-f]{8}$")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not cls._HEX8_RE.match(v):
            raise ValueError("id must be exactly 8 lowercase hex characters")
        return v


class PromptShortcuts(RootModel[tuple[PromptShortcutItem, ...]]):
    """
    Value object: the manual prompt shortcuts configured on a blueprint.

    Wire format is a JSON array [{id, text}, ...]. Immutable after construction.
    """
    root: tuple[PromptShortcutItem, ...] = ()

    @model_validator(mode="wrap")
    @classmethod
    def _raise_domain_validation_error(cls, data: object, handler) -> "PromptShortcuts":
        try:
            return handler(data)
        except ValidationError as exc:
            raise PromptShortcutsValidationError(
                format_validation_errors(exc),
            ) from exc
        except ValueError as exc:
            raise PromptShortcutsValidationError(str(exc)) from exc

    @model_validator(mode="after")
    def validate_collection(self) -> "PromptShortcuts":
        if len(self.root) > MAX_PROMPT_SHORTCUTS:
            raise PromptShortcutsValidationError(
                f"At most {MAX_PROMPT_SHORTCUTS} prompt shortcuts allowed",
            )
        ids = [p.id for p in self.root]
        if len(ids) != len(set(ids)):
            raise PromptShortcutsValidationError("Prompt shortcut ids must be unique")
        return self

    @property
    def prompts(self) -> tuple[PromptShortcutItem, ...]:
        """Alias for ``root`` — ergonomic access at call sites."""
        return self.root

    @model_serializer(mode="wrap")
    def _serialize(
        self,
        handler: SerializerFunctionWrapHandler,
        info: SerializationInfo,
    ) -> object:
        """JSON wire format is a flat array; empty collection serializes as null."""
        if info.mode == "json":
            return self.to_storage()
        return handler(self)

    # ── Factories ──

    @classmethod
    def parse(cls, raw: list | None) -> "PromptShortcuts":
        """Strict parse for write paths. Raises PromptShortcutsValidationError on invalid data."""
        if not raw:
            return cls(())
        try:
            return cls.model_validate(raw)
        except PromptShortcutsValidationError:
            raise
        except ValidationError as exc:
            raise PromptShortcutsValidationError(
                format_validation_errors(exc),
            ) from exc

    @classmethod
    def from_spec(cls, spec_dict: dict) -> "PromptShortcuts":
        """
        Extract from a raw spec_dict. Never raises.

        Legacy blueprints have no ``prompt_shortcuts`` key at all — returns empty.
        Current format: List[dict] with {id?, text}. Legacy ``kind`` keys are ignored.
        Duplicate ids and excess items beyond MAX_PROMPT_SHORTCUTS are dropped.
        """
        raw = spec_dict.get("prompt_shortcuts")
        if not raw or not isinstance(raw, list):
            return cls(())
        items: list[PromptShortcutItem] = []
        seen_ids: set[str] = set()
        for entry in raw:
            if not isinstance(entry, dict) or "text" not in entry:
                continue
            if len(items) >= MAX_PROMPT_SHORTCUTS:
                break
            try:
                item = PromptShortcutItem(**entry)
            except (ValueError, TypeError):
                continue
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)
            items.append(item)
        try:
            return cls(tuple(items))
        except (ValueError, TypeError):
            return cls(())

    @classmethod
    def from_raw_list(cls, raw: Optional[list]) -> "PromptShortcuts":
        """Construct from a raw list (as returned by the repository)."""
        if not raw or not isinstance(raw, list):
            return cls(())
        return cls.from_spec({"prompt_shortcuts": raw})

    # ── Serialization ──

    def to_storage(self) -> Optional[List[dict]]:
        """
        Serialize for persistence.
        Returns None when empty — signals the repo to $unset the key.
        """
        if not self.root:
            return None
        return [
            {"id": item.id, "text": item.text}
            for item in self.root
        ]

    # ── Queries ──

    @property
    def is_empty(self) -> bool:
        return len(self.root) == 0

    @property
    def is_full(self) -> bool:
        return len(self.root) >= MAX_PROMPT_SHORTCUTS

    @property
    def count(self) -> int:
        return len(self.root)
