"""RAG session-based authentication decorator.

Validates the Flask session cookie against the Redis server session.
Internal services may authenticate via the ``X-Authenticated-User`` header
(set after identity resolution at the calling service's entry point).

Endpoints read the authenticated username from ``g.user_id``.
"""
import logging

from flask import current_app, request

from global_utils.constants import INTERNAL_AUTH_HEADER
from global_utils.internal_auth import trusted_header_user
from global_utils.flask.decorators import require_team_session

logger = logging.getLogger(__name__)

_AUTH_HEADER = INTERNAL_AUTH_HEADER


def _get_internal_user() -> str | None:
    """Read the user identity stamped by a trusted internal service.

    Honoured only with the shared internal secret (or dev mode); see
    ``global_utils.internal_auth``.
    """
    user = trusted_header_user(request.headers)
    if user:
        logger.debug("Authenticated via %s header", _AUTH_HEADER)
    return user


rag_require_session = require_team_session(
    get_redis_store=lambda: current_app.extensions['redis_kv_store'],
    get_fallback_user=_get_internal_user,
)
