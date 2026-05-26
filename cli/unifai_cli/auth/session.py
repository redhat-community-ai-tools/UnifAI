"""Local auth session management.

Session is stored at ~/.unifai/session.json with a 10-hour TTL.
File permissions are set to 0o600 (owner read/write only).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

SESSION_DIR = Path.home() / ".unifai"
SESSION_FILE = SESSION_DIR / "session.json"
SESSION_TTL_HOURS = 10


def load_session() -> Optional[dict]:
    """Return the cached session if it exists and has not expired, else None."""
    if not SESSION_FILE.exists():
        return None
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        if datetime.now().timestamp() >= data.get("expires_at", 0):
            return None
        return data
    except Exception:
        return None


def save_session(user_info: dict) -> None:
    """Persist user info to disk with a 10-hour TTL."""
    SESSION_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = {
        "username": user_info.get("username", ""),
        "email": user_info.get("email", ""),
        "name": user_info.get("name", ""),
        "sub": user_info.get("sub", ""),
        "expires_at": (datetime.now() + timedelta(hours=SESSION_TTL_HOURS)).timestamp(),
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(SESSION_FILE, 0o600)


def clear_session() -> None:
    """Delete the local session file."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


def session_expires_at(session: dict) -> datetime:
    return datetime.fromtimestamp(session.get("expires_at", 0))
