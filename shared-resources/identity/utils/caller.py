"""Caller identification for the Identity HTTP API.

A request is attributed either to an authenticated end-user session or to a
trusted internal service (shared secret, see ``global_utils.internal_auth``).
Anything else is anonymous and refused by ``require_caller``.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Optional

from flask import current_app, g, jsonify, request

from global_utils.constants import INTERNAL_AUTH_HEADER
from global_utils.internal_auth import is_trusted_internal_request


@dataclass(frozen=True)
class Caller:
    username: str
    is_admin: bool = False
    is_service: bool = False


def _session_caller() -> Optional[Caller]:
    auth_manager = current_app.extensions.get("auth_manager")
    if auth_manager is None or not auth_manager.is_authenticated():
        return None
    user = auth_manager.get_user_info() or {}
    username = (user.get("username") or user.get("sub") or "").strip()
    if not username:
        return None
    return Caller(username=username, is_admin=bool(auth_manager._check_admin_permission(user)))


def current_caller() -> Optional[Caller]:
    """Return the caller of the current request, or ``None`` when anonymous."""
    cached = g.get("_identity_caller")
    if cached is not None:
        return cached
    caller = _session_caller()
    if caller is None and is_trusted_internal_request(request.headers):
        caller = Caller(
            username=(request.headers.get(INTERNAL_AUTH_HEADER) or "").strip(),
            is_service=True,
        )
    if caller is not None:
        g._identity_caller = caller
    return caller


def require_caller(f):
    """Refuse the request with 401 unless the caller is authenticated."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_caller() is None:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)

    return wrapper
