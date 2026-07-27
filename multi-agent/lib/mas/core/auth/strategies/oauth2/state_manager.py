"""
HMAC-signed state for OAuth redirects.

The state parameter travels through the user's browser, so it must be
tamper-proof and time-limited.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict


_DEFAULT_TTL = 600  # 10 minutes


class OAuthStateManager:
    """Create and validate HMAC-signed state tokens."""

    def __init__(self, secret: str, ttl_seconds: int = _DEFAULT_TTL):
        if not secret:
            raise ValueError("State signing secret must not be empty")
        self._secret = secret.encode()
        self._ttl = ttl_seconds

    def create_state(self, payload: Dict[str, Any]) -> str:
        payload_with_ts = {**payload, "_ts": int(time.time())}
        raw = json.dumps(payload_with_ts, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        return f"{raw}.{sig}"

    def validate_state(self, state: str) -> Dict[str, Any]:
        if "." not in state:
            raise ValueError("Malformed state — no signature separator")

        raw, sig = state.rsplit(".", 1)
        expected = hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("State signature mismatch — possible tampering")

        payload = json.loads(raw)
        ts = payload.pop("_ts", 0)
        if time.time() - ts > self._ttl:
            raise ValueError("State expired")

        return payload

    @staticmethod
    def hash_state(state: str) -> str:
        """Deterministic hash for use as a storage key (Redis / Mongo)."""
        return hashlib.sha256(state.encode()).hexdigest()
