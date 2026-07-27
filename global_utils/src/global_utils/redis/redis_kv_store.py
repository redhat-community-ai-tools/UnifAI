import logging
from typing import Any, Optional

from redis import Redis

from global_utils.ports.kv_store import KVStore

logger = logging.getLogger("redis_kv_store")


class RedisKVStore(KVStore):
    """Redis implementation of the KVStore port (hexagonal adapter)."""

    def __init__(self, client: Redis) -> None:
        self._client = client

    def ping(self) -> bool:
        return self._client.ping()

    def get(self, key: str) -> Optional[str]:
        raw = self._client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        # create a new key/value in redis
        if ttl_seconds is not None:
            self._client.set(key, value, ex=ttl_seconds)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        # delete a key from redis (delete the key and all its fields)
        self._client.delete(key)

    def hget(self, key: str) -> dict[str, Any]:
        # get the hash in redis
        return self._client.hgetall(key)

    def hset(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        # create a new hash in redis
        self._client.hset(key, mapping=value)
        if ttl_seconds is not None:
            self._client.expire(key, ttl_seconds)

    def hdel(self, key: str, field: str) -> None:
        # delete a field from a hash in redis
        self._client.hdel(key, field)
