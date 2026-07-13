"""RAG session-based authentication decorator.

Validates the Flask session cookie against the Redis server session.
Endpoints read the authenticated username from ``g.user_id``.
"""
from flask import current_app

from global_utils.flask.decorators import require_team_session

rag_require_session = require_team_session(
    get_redis_store=lambda: current_app.extensions['redis_kv_store'],
)
