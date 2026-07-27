"""Shared utilities — layer-neutral helpers usable by both adapters and services."""

from __future__ import annotations

import shutil
from datetime import timedelta


def resolve_bash() -> str:
    """Find bash on PATH instead of assuming /bin/bash."""
    path = shutil.which("bash")
    if not path:
        raise RuntimeError(
            "bash not found on PATH. Install bash or set SHELL to a compatible shell."
        )
    return path


def format_duration(delta: timedelta) -> str:
    """Format a timedelta as a compact human-readable string like '2h 15m'."""
    total_seconds = int(delta.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_min}m" if remaining_min else f"{hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours}h" if remaining_hours else f"{days}d"
