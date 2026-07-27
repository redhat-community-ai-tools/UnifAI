"""
Auth-layer errors.

All custom exceptions inherit from :class:`AuthError` so callers can
catch the entire family with a single ``except AuthError``.
"""


class AuthError(Exception):
    """Base class for all auth-layer errors."""


class TokenExpiredError(AuthError):
    """Token is expired and no automatic refresh is possible."""


class TokenEndpointError(AuthError):
    """Token endpoint returned an error (exchange or refresh)."""


class TokenRefreshError(TokenEndpointError):
    """Refresh attempt failed (network, revoked grant, …)."""


class AuthDetectionError(AuthError):
    """Something went wrong while detecting a server's auth requirements."""


class AuthNotConfiguredError(AuthError):
    """Expected auth configuration is missing or incomplete."""


class InvalidStateError(AuthError):
    """OAuth state parameter is invalid, tampered with, or expired."""


class FlowStateNotFoundError(AuthError):
    """No pending flow state for the given state hash (consumed or expired)."""


class ClientRegistrationError(AuthError):
    """Dynamic Client Registration (RFC 7591) failed."""
