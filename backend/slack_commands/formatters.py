"""Slack response formatters — convert domain data to Slack-friendly output."""
import math
from typing import List

from slack_commands.models import SlackResponse

STATUS_EMOJI = {
    "COMPLETED": ":white_check_mark:",
    "RUNNING": ":arrows_counterclockwise:",
    "QUEUED": ":hourglass:",
    "PENDING": ":clock3:",
    "FAILED": ":x:",
    "CANCELLED": ":no_entry_sign:",
    "LOCKED": ":lock:",
    "IN_USE": ":arrows_counterclockwise:",
}

ROLE_EMOJI = {
    "user": ":bust_in_silhouette:",
    "human": ":bust_in_silhouette:",
    "assistant": ":robot_face:",
    "ai": ":robot_face:",
    "system": ":gear:",
    "tool": ":wrench:",
}


def format_session_list(
    sessions: List[dict], page: int = 1, page_size: int = 10
) -> SlackResponse:
    """Format a paginated list of session documents into a Slack message."""
    if not sessions:
        return SlackResponse(text=":inbox_tray: You have no sessions yet.")

    total = len(sessions)
    total_pages = math.ceil(total / page_size)
    page = max(1, min(page, total_pages))

    start = (page - 1) * page_size
    end = start + page_size
    page_sessions = sessions[start:end]

    lines = [f"*Your Sessions* ({total} total — page {page}/{total_pages})\n"]

    for session in page_sessions:
        session_id = session.get("session_id") or session.get("run_id") or "?"
        status = str(session.get("status") or "unknown")
        blueprint_id = session.get("blueprint_id", "")
        title = (
            session.get("title")
            or session.get("metadata", {}).get("title")
            or ""
        )

        emoji = STATUS_EMOJI.get(status.upper(), ":grey_question:")
        label = title if title else blueprint_id or "untitled"

        lines.append(f"{emoji} `{session_id}` — {label} ({status})")

    if total_pages > 1 and page < total_pages:
        lines.append(f"\n_Type `/unifai list {page + 1}` for next page_")

    return SlackResponse(text="\n".join(lines))


def format_workflow_list(workflows: list) -> SlackResponse:
    """Format a list of workflow dicts into a Slack message."""
    if not workflows:
        return SlackResponse(text=":inbox_tray: No workflows available.")

    lines = [f"*Available Workflows* ({len(workflows)} total)\n"]

    for wf in workflows[:15]:
        wf_id = wf.get("blueprint_id", "?")
        name = wf.get("name") or wf.get("spec_dict", {}).get("name") or wf_id
        description = wf.get("description") or ""

        desc_suffix = f" — _{description}_" if description else ""
        lines.append(f":blue_book: `{wf_id}` — *{name}*{desc_suffix}")

    if len(workflows) > 15:
        lines.append(f"\n_…and {len(workflows) - 15} more_")

    return SlackResponse(text="\n".join(lines))
