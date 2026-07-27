"""
Aggregator for OpenAI streaming tool call deltas.

The OpenAI streaming API sends tool call information as incremental
fragments across multiple chunks.  This module reassembles them into
complete ToolCall domain objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..common.chat.message import ToolCall


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
        return [
            frag.to_tool_call()
            for frag in self._fragments.values()
        ]
