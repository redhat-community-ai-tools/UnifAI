"""
Aggregator for OpenAI Responses API streaming events.

Unlike Chat Completions (which sends content and tool-call deltas on a
single ``choices[].delta`` object), the Responses API emits discrete typed
events:

  - ``response.output_text.delta`` – incremental text token
  - ``response.function_call_arguments.delta`` – incremental tool-call args
  - ``response.function_call_arguments.done`` – completed tool-call
  - ``response.output_item.done`` – completed output item (text or tool-call)
  - ``response.completed`` – final event with usage data
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..common.chat.message import ToolCall


@dataclass
class _FunctionCallFragment:
    """Accumulates data for a single function call across stream events."""
    item_id: str = ""
    name: str = ""
    arguments: str = ""
    call_id: str = ""

    def to_tool_call(self) -> ToolCall:
        return ToolCall(
            name=self.name,
            args=json.loads(self.arguments) if self.arguments else {},
            tool_call_id=self.call_id or self.item_id,
        )


class ResponsesStreamAggregator:
    """Collects Responses API streaming events and produces domain objects.

    Usage::

        agg = ResponsesStreamAggregator()
        for event in stream:
            text = agg.process(event)
            if text:
                yield text
        if agg.has_tool_calls:
            tool_calls = agg.build()
    """

    def __init__(self) -> None:
        self._fragments: Dict[str, _FunctionCallFragment] = {}
        self._content: str = ""
        self._usage: Optional[Dict[str, int]] = None

    @property
    def accumulated_content(self) -> str:
        return self._content

    @property
    def has_tool_calls(self) -> bool:
        return bool(self._fragments)

    @property
    def usage(self) -> Optional[Dict[str, int]]:
        return self._usage

    def process(self, event: Any) -> Optional[str]:
        """Process a single stream event. Returns text delta if available."""
        t = event.type

        if t == "response.output_text.delta":
            self._content += event.delta
            return event.delta

        if t == "response.function_call_arguments.delta":
            frag = self._fragments.setdefault(
                event.item_id, _FunctionCallFragment(item_id=event.item_id),
            )
            frag.arguments += event.delta

        elif t == "response.function_call_arguments.done":
            frag = self._fragments.setdefault(
                event.item_id, _FunctionCallFragment(item_id=event.item_id),
            )
            frag.name = event.name
            frag.arguments = event.arguments

        elif t == "response.output_item.done":
            item = event.item
            if getattr(item, "type", None) == "function_call":
                frag = self._fragments.setdefault(
                    item.id or item.call_id,
                    _FunctionCallFragment(item_id=item.id or ""),
                )
                frag.name = item.name
                frag.arguments = item.arguments
                frag.call_id = item.call_id

        elif t == "response.completed":
            if hasattr(event, "response") and hasattr(event.response, "usage"):
                u = event.response.usage
                if u:
                    self._usage = {
                        "input_tokens": u.input_tokens,
                        "output_tokens": u.output_tokens,
                        "total_tokens": u.total_tokens,
                    }

        return None

    def build(self) -> Optional[List[ToolCall]]:
        """Return assembled ToolCall list, or *None* if nothing was collected."""
        if not self._fragments:
            return None
        return [frag.to_tool_call() for frag in self._fragments.values()]
