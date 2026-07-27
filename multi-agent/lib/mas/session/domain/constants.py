"""
Session domain constants.

Centralises magic strings used across the session lifecycle
so that writers (SessionLifecycle) and clearers (SessionInputProjector)
stay in sync via a single source of truth.
"""

CANCELLED_TAG = "cancelled"
CANCELLED_STATUS_MESSAGE = "Workflow was stopped by user."
