"""
Redis-backed channel factory.

Creates session-scoped writers, readers, and a shared monitor,
all backed by Redis Streams. A single connection pool is shared.

``create_input_capable()`` returns a ``RedisInputCapableChannel``
that supports cross-process HITL via Redis ``BLPOP``/``LPUSH``.
"""
import json
from typing import Optional

from pydantic.json import pydantic_encoder
from redis import ConnectionPool, Redis

from mas.core.channels import (
    ChannelFactory,
    InputCapableChannel,
    SessionChannel,
    SessionChannelReader,
    SessionStreamMonitor,
)
from .channel import RedisSessionChannel
from .input_channel import RedisInputCapableChannel, _HITL_KEY_PREFIX, _HITL_RESPONSE_TTL_S
from .reader import RedisSessionChannelReader
from .monitor import RedisStreamMonitor


class RedisChannelFactory(ChannelFactory):

    def __init__(
        self,
        redis_url: str,
        stream_ttl: int = 3600,
        block_ms: int = 5000,
        batch_size: int = 50,
    ) -> None:
        self._pool = ConnectionPool.from_url(redis_url, socket_timeout=30)
        self._stream_ttl = stream_ttl
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._monitor: Optional[RedisStreamMonitor] = None

    def _redis(self) -> Redis:
        return Redis(connection_pool=self._pool)

    def create(self, session_id: str) -> SessionChannel:
        return RedisSessionChannel(
            session_id,
            self._redis(),
            ttl=self._stream_ttl,
        )

    def create_input_capable(
        self,
        session_id: str,
    ) -> InputCapableChannel:
        return RedisInputCapableChannel(
            session_id,
            self._redis(),
            ttl=self._stream_ttl,
        )

    def get_input_channel(self, session_id: str) -> "_RedisSubmitProxy":
        """Return a lightweight proxy that can only ``submit()`` HITL
        responses.

        With Redis the state lives in a shared key, so no in-memory
        registry is needed (unlike LocalChannelFactory).  The proxy
        avoids the full ``RedisInputCapableChannel.__init__`` which
        resets gate keys and registers the session as active.
        """
        return _RedisSubmitProxy(session_id, self._redis())

    def create_reader(self, session_id: str) -> SessionChannelReader:
        return RedisSessionChannelReader(
            session_id,
            self._redis(),
            block_ms=self._block_ms,
            batch_size=self._batch_size,
        )

    def create_monitor(self) -> SessionStreamMonitor:
        if self._monitor is None:
            self._monitor = RedisStreamMonitor(self._redis())
        return self._monitor


class _RedisSubmitProxy:
    """Minimal object that can only ``submit()`` an HITL response.

    Used by the API endpoint to push a response into the Redis list
    that the running ``RedisInputCapableChannel.wait_for()`` is
    blocking on — without touching any session-lifecycle state.
    """

    def __init__(self, session_id: str, redis_client: Redis) -> None:
        self._session_id = session_id
        self._redis = redis_client

    def submit(self, request_id: str, data: dict) -> None:
        key = f"{_HITL_KEY_PREFIX}{self._session_id}:{request_id}"
        self._redis.lpush(key, json.dumps(data, default=pydantic_encoder))
        self._redis.expire(key, _HITL_RESPONSE_TTL_S)
