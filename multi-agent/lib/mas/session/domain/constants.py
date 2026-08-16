"""
Session domain constants.

Centralises magic strings used across the session lifecycle
so that writers (SessionLifecycle) and clearers (SessionInputProjector)
stay in sync via a single source of truth.
"""

CANCELLED_TAG = "cancelled"
CANCELLED_STATUS_MESSAGE = "Workflow was stopped by user."

# Default page size for paginated session listings. Shared across every layer
# (Flask endpoint, session service manager, repository port, and Mongo adapter)
# so the default stays consistent end to end.
DEFAULT_SESSION_PAGE_SIZE = 50
