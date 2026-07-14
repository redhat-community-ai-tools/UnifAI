"""RAG session-based authentication decorator.

Validates the Flask session cookie against the Redis server session.
Internal services may authenticate via the ``X-Authenticated-User`` header
(set after identity resolution at the calling service's entry point).

Endpoints read the authenticated username from ``g.user_id``.
"""
import logging

from flask import current_app, request

from global_utils.constants import INTERNAL_AUTH_HEADER
from global_utils.flask.decorators import require_team_session

logger = logging.getLogger(__name__)

_AUTH_HEADER = INTERNAL_AUTH_HEADER


def _get_internal_user() -> str | None:
    """Read user identity from internal service header.

    Internal services (MAS, Slack WS, etc.) stamp this header after
    resolving the caller's identity at their own entry point.  External
    traffic carrying this header is blocked at the Nginx gateway.
    """
    user = request.headers.get(_AUTH_HEADER, "").strip()
    if user:
        logger.debug("Authenticated via %s header", _AUTH_HEADER)
    return user or None


rag_require_session = require_team_session(
    get_redis_store=lambda: current_app.extensions['redis_kv_store'],
    get_fallback_user=_get_internal_user,
)
