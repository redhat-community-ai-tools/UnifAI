"""
Redis input-capable session channel for cross-process HITL.

Extends ``RedisSessionChannel`` with bidirectional I/O.

Outbound events use the existing Redis Stream (``XADD``).
Inbound HITL responses use a per-request Redis list with ``BLPOP``
so that ``wait_for`` blocks efficiently across processes.

``wait_for`` uses a short inner BLPOP timeout (5 s) and loops so
it can check the ``_closed`` flag and respect the overall timeout.
Temporal activity heartbeating is handled by the ``@heartbeat``
decorator on the activity — no callback needed here.
"""
import json
import logging
import threading
from typing import Any, Optional

from pydantic.json import pydantic_encoder
from redis import Redis

from mas.core.channels import InputCapableChannel
from .constants import (
    STREAM_PREFIX,
    ACTIVE_SESSIONS_KEY,
    CANCEL_GATE_PREFIX,
    StreamField,
    ControlSignal,
)

logger = logging.getLogger(__name__)

_GATE_TTL_S = 300
_HITL_KEY_PREFIX = "mas:hitl:"
_HITL_RESPONSE_TTL_S = 600
_BLPOP_SLICE_S = 5


class RedisInputCapableChannel(InputCapableChannel):
    """Bidirectional Redis channel — outbound via Streams,
    inbound HITL responses via ``BLPOP`` on per-request keys."""

    def __init__(
        self,
        session_id: str,
        redis_client: Redis,
        ttl: int = 3600,
    ) -> None:
        self._session_id = session_id
        self._redis = redis_client
        self._stream_key = f"{STREAM_PREFIX}{session_id}"
        self._gate_key = f"{CANCEL_GATE_PREFIX}{session_id}"
        self._ttl = ttl
        self._closed = False
        self._close_lock = threading.Lock()

        self._redis.delete(self._gate_key)
        self._redis.sadd(ACTIVE_SESSIONS_KEY, session_id)

    # -- SessionChannel (outbound) -----------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    def emit(self, data: Any) -> None:
        if self._closed:
            return
        if self._redis.exists(self._gate_key):
            self._closed = True
            return
        self._redis.xadd(
            self._stream_key,
            {StreamField.PAYLOAD: json.dumps(data, default=pydantic_encoder)},
        )
        self._touch_ttl()

    def is_active(self) -> bool:
        return not self._closed

    def close(self, *, cancelled: bool = False) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        if cancelled:
            self._redis.set(self._gate_key, "1", ex=_GATE_TTL_S)
        self._redis.xadd(
            self._stream_key,
            {StreamField.CONTROL: ControlSignal.CLOSE},
        )
        self._redis.srem(ACTIVE_SESSIONS_KEY, self._session_id)
        self._redis.delete(self._stream_key)

    # -- InputCapableChannel (inbound HITL) ---------------------------------

    def wait_for(self, request_id: str, timeout: float) -> Optional[dict]:
        key = self._hitl_key(request_id)
        remaining = timeout

        while remaining > 0 and not self._closed:
            slice_timeout = min(_BLPOP_SLICE_S, remaining)
            result = self._redis.blpop(key, timeout=int(slice_timeout))

            if result is not None:
                _, raw = result
                return json.loads(raw)

            remaining -= slice_timeout

        return None

    def submit(self, request_id: str, data: dict) -> None:
        key = self._hitl_key(request_id)
        self._redis.lpush(key, json.dumps(data, default=pydantic_encoder))
        self._redis.expire(key, _HITL_RESPONSE_TTL_S)

    # -- Internal -----------------------------------------------------------

    def _hitl_key(self, request_id: str) -> str:
        return f"{_HITL_KEY_PREFIX}{self._session_id}:{request_id}"

    def _touch_ttl(self) -> None:
        if self._ttl > 0:
            self._redis.expire(self._stream_key, self._ttl)
