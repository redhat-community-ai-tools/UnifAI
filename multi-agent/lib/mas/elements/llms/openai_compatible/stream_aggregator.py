"""
Aggregator for OpenAI Chat Completions streaming tool call deltas.

The Chat Completions streaming API sends tool call information as incremental
fragments across multiple chunks. This module reassembles them into
complete ToolCall domain objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..common.chat.message import RESPONSE_METADATA_KEY, ToolCall


@dataclass
class _ToolCallFragment:
    """Accumulates partial data for a single tool call across stream chunks."""
    id: str = ""
    name: str = ""
    arguments: str = ""

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            name=self.name,
            args=json.loads(self.arguments) if self.arguments else {},
            tool_call_id=self.id,
        )


class StreamToolCallAggregator:
    """Collects streaming tool-call deltas and produces final ToolCall objects.

    Usage::

        agg = StreamToolCallAggregator()
        for chunk in stream:
            if chunk.choices[0].delta.tool_calls:
                agg.absorb(chunk.choices[0].delta.tool_calls)
        tool_calls = agg.build()  # None if no tool calls were received
    """

    def __init__(self) -> None:
        self._fragments: Dict[int, _ToolCallFragment] = {}

    @property
    def has_tool_calls(self) -> bool:
        return bool(self._fragments)

    def absorb(self, deltas: list) -> None:
        """Merge a list of ``ChoiceDeltaToolCall`` objects into the accumulator."""
        for delta in deltas:
            frag = self._fragments.setdefault(delta.index, _ToolCallFragment())
            if delta.id:
                frag.id = delta.id
            if delta.function:
                if delta.function.name:
                    frag.name += delta.function.name
                if delta.function.arguments:
                    frag.arguments += delta.function.arguments

    def build(self) -> Optional[List[ToolCall]]:
        """Return assembled ToolCall list, or *None* if nothing was collected."""
        if not self._fragments:
            return None
        return [frag.to_tool_call() for frag in self._fragments.values()]


def extract_extra_fields(obj: object) -> Dict[str, Any]:
    """Return the non-standard top-level fields of an SDK response/chunk.

    The OpenAI SDK models accept unknown fields and expose them through
    ``model_extra``.  Names are preserved exactly as the server sent them.
    """
    extra = getattr(obj, "model_extra", None)
    return dict(extra) if isinstance(extra, dict) else {}


class StreamMetadataCollector:
    """Collects the response id and non-standard fields across stream chunks.

    Servers may repeat the extra fields on every chunk or only on one; later
    chunks win on conflicting keys.
    """

    def __init__(self) -> None:
        self.response_id: Optional[str] = None
        self.model: Optional[str] = None
        self.fields: Dict[str, Any] = {}

    def absorb(self, chunk: object) -> None:
        rid = getattr(chunk, "id", None)
        if isinstance(rid, str) and rid:
            self.response_id = rid
        model = getattr(chunk, "model", None)
        if isinstance(model, str) and model:
            self.model = model
        self.fields.update(extract_extra_fields(chunk))


def build_response_metadata(
    response_id: Optional[str],
    model: Optional[str],
    fields: Dict[str, Any],
    lookup_url_template: Optional[str],
) -> Dict[str, Any]:
    """Build the ``ChatMessage.metadata`` entry, or ``{}`` when nothing applies.

    Metadata is only produced when the server returned non-standard fields or
    a ``metadata_lookup_url`` is configured, so endpoints that return plain
    OpenAI responses see no behaviour change.
    """
    lookup_url = None
    if lookup_url_template and response_id:
        lookup_url = lookup_url_template.replace("{response_id}", response_id)
    if not fields and not lookup_url:
        return {}
    entry: Dict[str, Any] = {"response_id": response_id, "model": model, "fields": fields}
    if lookup_url:
        entry["lookup_url"] = lookup_url
    return {RESPONSE_METADATA_KEY: entry}
