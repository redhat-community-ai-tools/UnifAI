#!/usr/bin/env python3
"""Cursor hook handler that sends tracing data to Langfuse.

Each hook invocation is a separate process. All observations for a single
agent conversation are grouped under one Langfuse trace using a deterministic
trace ID derived from the conversation_id.

Environment variables (must be set before the agent runs):
    LANGFUSE_PUBLIC_KEY  – Langfuse public key
    LANGFUSE_SECRET_KEY  – Langfuse secret key
    LANGFUSE_BASE_URL    – Langfuse API URL (optional, defaults to cloud)
"""

from __future__ import annotations

import json
import os
import sys


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return
        payload: dict = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        return

    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get("LANGFUSE_SECRET_KEY"):
        return

    event = payload.get("hook_event_name", "")
    conversation_id = payload.get("conversation_id", "")
    if not event or not conversation_id:
        return

    handler = _HANDLERS.get(event)
    if not handler:
        return

    try:
        from langfuse import Langfuse

        langfuse = Langfuse()
        trace_id = langfuse.create_trace_id(seed=conversation_id)
        handler(langfuse, trace_id, payload)
        langfuse.flush()
    except Exception as exc:
        print(f"::warning::Langfuse hook failed: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Handler per hook event
# ---------------------------------------------------------------------------


def _handle_session_start(langfuse, trace_id: str, payload: dict) -> None:
    from langfuse import propagate_attributes

    session_id = payload.get("session_id", payload.get("conversation_id", ""))
    model = payload.get("model", "")

    pr_number = os.environ.get("PR_NUMBER", "")
    branch = os.environ.get("BRANCH_REF", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = ""
    if run_id:
        server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        run_url = f"{server}/{repo}/actions/runs/{run_id}"

    tags = ["pipeline", "ci"]
    if pr_number:
        tags.append(f"pr-{pr_number}")

    with propagate_attributes(
        user_id="pipeline-ci",
        session_id=session_id,
        tags=tags,
    ):
        with langfuse.start_as_current_observation(
            name="pipeline-review",
            as_type="span",
            trace_context={"trace_id": trace_id},
            input={
                "command": "/pipeline review",
                "model": model,
                "pr_number": pr_number,
                "branch": branch,
            },
        ) as span:
            span.update(
                metadata={
                    "source": "cursor-pipeline",
                    "cursor_version": payload.get("cursor_version", ""),
                    "run_id": run_id,
                    "run_url": run_url,
                    "is_background_agent": payload.get("is_background_agent", False),
                    "composer_mode": payload.get("composer_mode", ""),
                },
            )


def _handle_post_tool_use(langfuse, trace_id: str, payload: dict) -> None:
    tool_name = payload.get("tool_name", "unknown")

    # subagentStop provides richer data for Task tools
    if tool_name == "Task":
        return

    tool_output_raw = payload.get("tool_output", "")
    try:
        tool_output = (
            json.loads(tool_output_raw)
            if isinstance(tool_output_raw, str)
            else tool_output_raw
        )
    except (json.JSONDecodeError, TypeError):
        tool_output = tool_output_raw

    if isinstance(tool_output, str) and len(tool_output) > 10_000:
        tool_output = tool_output[:10_000] + "... [truncated]"

    with langfuse.start_as_current_observation(
        name=f"tool:{tool_name}",
        as_type="span",
        trace_context={"trace_id": trace_id},
        input=payload.get("tool_input"),
    ) as span:
        span.update(
            output=tool_output,
            metadata={
                "tool_use_id": payload.get("tool_use_id", ""),
                "duration_ms": payload.get("duration", 0),
                "cwd": payload.get("cwd", ""),
                "model": payload.get("model", ""),
            },
        )


def _handle_subagent_stop(langfuse, trace_id: str, payload: dict) -> None:
    subagent_type = payload.get("subagent_type", "unknown")
    status = payload.get("status", "unknown")
    summary = payload.get("summary", "")

    if isinstance(summary, str) and len(summary) > 20_000:
        summary = summary[:20_000] + "... [truncated]"

    with langfuse.start_as_current_observation(
        name=f"subagent:{subagent_type}",
        as_type="span",
        trace_context={"trace_id": trace_id},
        input={
            "task": payload.get("task", ""),
            "description": payload.get("description", ""),
        },
    ) as span:
        span.update(
            output={"summary": summary, "status": status},
            metadata={
                "subagent_type": subagent_type,
                "duration_ms": payload.get("duration_ms", 0),
                "message_count": payload.get("message_count", 0),
                "tool_call_count": payload.get("tool_call_count", 0),
                "modified_files": payload.get("modified_files", []),
                "loop_count": payload.get("loop_count", 0),
            },
        )


def _handle_stop(langfuse, trace_id: str, payload: dict) -> None:
    status = payload.get("status", "unknown")

    with langfuse.start_as_current_observation(
        name="agent-stop",
        as_type="span",
        trace_context={"trace_id": trace_id},
    ) as span:
        span.update(
            output={"status": status},
            metadata={
                "loop_count": payload.get("loop_count", 0),
                "model": payload.get("model", ""),
            },
        )


def _handle_session_end(langfuse, trace_id: str, payload: dict) -> None:
    with langfuse.start_as_current_observation(
        name="session-end",
        as_type="span",
        trace_context={"trace_id": trace_id},
    ) as span:
        span.update(
            output={
                "reason": payload.get("reason", ""),
                "final_status": payload.get("final_status", ""),
            },
            metadata={
                "duration_ms": payload.get("duration_ms", 0),
                "is_background_agent": payload.get("is_background_agent", False),
            },
        )


_HANDLERS = {
    "sessionStart": _handle_session_start,
    "postToolUse": _handle_post_tool_use,
    "subagentStop": _handle_subagent_stop,
    "stop": _handle_stop,
    "sessionEnd": _handle_session_end,
}

if __name__ == "__main__":
    main()
