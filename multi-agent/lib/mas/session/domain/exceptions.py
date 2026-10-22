import re


class SessionCancelledException(Exception):
    """Engine-agnostic cancellation signal.

    Each engine adapter translates its native cancel mechanism
    (Temporal CancelledError, Celery SoftTimeLimitExceeded, etc.)
    into this exception inside its ops methods.
    The BackgroundSessionRunner catches it and calls ops.cancel().
    """
    pass


class SessionAlreadyCancelledError(Exception):
    """Raised when a session is already in CANCELLED state at begin() time."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' is already cancelled")


class ScheduledSessionCancelledException(Exception):
    """Engine-agnostic cancellation signal for scheduled session execution.

    Each engine adapter translates its native cancel mechanism into this
    exception inside its ScheduledRunOps methods. The ScheduledSessionRunner
    catches it, records CANCELLED, and re-raises.
    """
    pass


class ScheduledSessionSetupError(Exception):
    """Raised when scheduled session provisioning fails before a session_id is available."""

    def __init__(self, reason: str | None = None):
        self.reason = reason
        msg = "Scheduled session setup failed"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


class SessionBlueprintError(Exception):
    """Base class for session blueprint-related errors."""
    pass


class BlueprintNotFoundError(SessionBlueprintError):
    """Raised when a blueprint required by a session is not found or has been deleted."""
    
    def __init__(self, blueprint_id: str, session_id: str = None):
        self.blueprint_id = blueprint_id
        self.session_id = session_id
        
        if session_id:
            msg = f"Cannot load session '{session_id}': Blueprint '{blueprint_id}' has been deleted"
        else:
            msg = f"Blueprint '{blueprint_id}' does not exist or has been deleted"
            
        super().__init__(msg)


BUILD_ERROR_MESSAGE_LIMIT = 200

_IDENT = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_SCRUBBERS = (
    (re.compile(r"\s*\|\s*config=.*", re.DOTALL), ""),
    (re.compile(r"\{[^{}]*\}"), "<redacted>"),
    (re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://\S+"), "<redacted>"),
    (re.compile(r"(?i)\b(bearer|basic)\s+\S+"), r"\1 <redacted>"),
    (re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization)\b\s*[=:]\s*\S+"), r"\1=<redacted>"),
    (re.compile(r"(?<![\w/])/[\w.\-@]+(?:/[\w.\-@]+)+"), "<redacted>"),
    (re.compile(r"\b[\w\-]+(?:\.[\w\-]+)+(?::\d+)?\b"), "<redacted>"),
    (re.compile(r"\b[\w\-]+:\d{2,5}\b"), "<redacted>"),
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"), "<redacted>"),
    (re.compile(r"\b(?=[A-Za-z_\-]*\d)[A-Za-z0-9_\-]{16,}\b"), "<redacted>"),
)


def scrub_error_message(text: object, limit: int = BUILD_ERROR_MESSAGE_LIMIT) -> str:
    """Defence in depth for anything stored in session metadata or sent in an HTTP body.

    Drops a ``| config=...`` tail, braces blocks, URLs (userinfo included), host names,
    file paths and token-looking values, then caps the length. The safe message built by
    :func:`session_build_error_message` never needs it; it protects against a message that
    was assembled elsewhere (an older worker, another error source).
    """
    out = text if isinstance(text, str) else ""
    for pattern, repl in _SCRUBBERS:
        out = pattern.sub(repl, out)
    return out[:limit]


def _chain(e: BaseException) -> list:
    chain, seen = [], set()
    cur = e
    while cur is not None and id(cur) not in seen and len(chain) < 10:
        chain.append(cur)
        seen.add(id(cur))
        cur = cur.__cause__ or cur.__context__
    return chain


_UNREACHABLE_HINTS = ("connect", "timeout", "unreach", "serverselection", "refused", "network", "dns")
_INVALID_HINTS = ("validation", "config", "value", "type", "key", "attribute", "reject")


def _reason(root: BaseException) -> str:
    names = [c.__name__.lower() for c in type(root).__mro__ if c is not object]
    if isinstance(root, (OSError, TimeoutError)) or any(h in n for n in names for h in _UNREACHABLE_HINTS):
        return "dependency unreachable"
    if any(h in n for n in names for h in _INVALID_HINTS):
        return "invalid configuration"
    return "build error"


def session_build_error_message(e: BaseException, uid: str | None = None) -> str:
    """Safe, short description of an element build failure.

    Built only from structured data: the element category/type (``element_type`` set at
    raise time) or the node ``uid``, the exception class names and a generic reason. The
    exception text and the element config (which can carry hosts, ids, URLs with
    credentials) are never used; they stay in the server log.
    """
    chain = _chain(e)
    root = chain[-1]
    element = next((c for c in chain if getattr(c, "element_type", None)), None)
    what = None
    if element is not None:
        etype = element.element_type
        cat = getattr(element, "category", None)
        if isinstance(etype, str) and _IDENT.match(etype):
            what = f"{cat} '{etype}'" if isinstance(cat, str) and _IDENT.match(cat) else f"'{etype}'"
    if what is None and uid and _IDENT.match(uid):
        what = f"node '{uid}'"
    names = type(e).__name__ if root is e else f"{type(e).__name__} <- {type(root).__name__}"
    message = "Session build failed" + (f" for {what}" if what else "") + f": {_reason(root)} ({names})"
    return scrub_error_message(message)


class SessionBuildError(Exception):
    """Raised when a session's elements cannot be built (e.g. a misconfigured tool).

    ``message`` is safe to show to the caller (scrubbed: no configuration values, no
    traceback); the original exception is chained as ``__cause__`` for server-side logging.
    """

    error_type = "session_build_failed"

    def __init__(self, session_id: str, message: str):
        self.session_id = session_id
        self.message = scrub_error_message(message)
        super().__init__(self.message)
