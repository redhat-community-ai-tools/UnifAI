"""
Real-time display of streaming events during workflow execution.

Handles NDJSON streaming responses from the MAS API.
Event types emitted by nodes:
  - llm_token: Incremental LLM output tokens
  - tool_calling: Tool invocation notifications
  - complete: Node completion with state
  - heartbeat: Keep-alive (ignored)
  - agent_*: Agent step events
"""
from __future__ import annotations

import json
from typing import Iterator

from rich.console import Console


def iter_ndjson(response) -> Iterator[dict]:
    """Iterate over NDJSON lines from a streaming HTTP response."""
    for line in response.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def display_streaming_events(response, console: Console) -> bool:
    """
    Read NDJSON events from a streaming HTTP response and display
    them in real time.

    Returns True on ``stream_end``, False on ``stream_error`` or early close.
    """
    current_node = None

    for event in iter_ndjson(response):
        if not isinstance(event, dict):
            continue

        event_type = event.get("type", "")

        if event_type == "heartbeat":
            continue

        if event_type == "stream_end":
            if current_node is not None:
                console.print()
            return True

        if event_type == "stream_error":
            if current_node is not None:
                console.print()
            error = event.get("error", "Unknown stream error")
            console.print(f"  [red]Stream error:[/red] {error}")
            return False

        if event_type == "llm_token":
            node = event.get("display_name") or event.get("node", "")
            chunk = event.get("chunk", "")

            if node != current_node:
                if current_node is not None:
                    console.print()
                console.print(f"  [bold cyan]{node}[/bold cyan]: ", end="")
                current_node = node

            console.print(chunk, end="", highlight=False)

        elif event_type == "tool_calling":
            if current_node is not None:
                console.print()
                current_node = None

            tool_name = event.get("tool", "unknown")
            node = event.get("display_name") or event.get("node", "")
            console.print(f"  [dim][{node}] calling tool:[/dim] [yellow]{tool_name}[/yellow]")

        elif event_type == "complete":
            if current_node is not None:
                console.print()
                current_node = None

            node = event.get("display_name") or event.get("node", "")
            console.print(f"  [dim][{node}] completed[/dim]")

        elif event_type.startswith("agent_"):
            if current_node is not None:
                console.print()
                current_node = None

            node = event.get("display_name") or event.get("node", "")
            step = event_type.replace("agent_", "")
            console.print(f"  [dim][{node}] agent {step}[/dim]")

    if current_node is not None:
        console.print()
    return True
