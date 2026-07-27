"""
RedisFlowStateStore — implements :class:`FlowStateStore` using Redis.

Keys: ``auth_pending:<state_hash>``
TTL:  derived from ``flow_state.expires_at``
Consume: atomic ``GETDEL`` (Redis 6.2+)

When an encryption key is provided, the JSON payload is encrypted at rest
so that PKCE verifiers and user identifiers are not exposed in Redis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from mas.core.auth.strategies.oauth2.models import FlowState, FlowStateStore

logger = logging.getLogger(__name__)

_PREFIX = "auth_pending:"


class RedisFlowStateStore(FlowStateStore):

    def __init__(self, redis_client, encryption_key: str = ""):
        self._redis = redis_client
        self._fernet = None
        if encryption_key:
            from cryptography.fernet import Fernet
            self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def save(self, flow_state: FlowState) -> None:
        key = f"{_PREFIX}{flow_state.state_hash}"
        ttl = max(
            int((flow_state.expires_at - datetime.now(timezone.utc)).total_seconds()),
            60,
        )
        payload = json.dumps(flow_state.model_dump(mode="json"))
        if self._fernet:
            payload = self._fernet.encrypt(payload.encode()).decode()
        self._redis.setex(key, ttl, payload)

    def consume(self, state_hash: str) -> Optional[FlowState]:
        key = f"{_PREFIX}{state_hash}"
        raw = self._redis.getdel(key)
        if raw is None:
            return None
        try:
            if isinstance(raw, bytes):
                raw = raw.decode()
            if self._fernet and raw.startswith("gAAAAAB"):
                raw = self._fernet.decrypt(raw.encode()).decode()
            data = json.loads(raw)
            return FlowState.model_validate(data)
        except Exception as exc:
            logger.error("Failed to parse pending auth from Redis: %s", exc)
            return None
