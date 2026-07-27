"""
Redis client factory for shared services.

Uses :class:`~global_utils.config.config.SharedConfig` for host, port, password,
and ``decode_responses``. :func:`build_redis_client` returns a process-wide
**cached** :class:`redis.Redis` per distinct ``db`` (see the function docstring);
call ``build_redis_client.cache_clear()`` in tests to reset.
"""
from __future__ import annotations

import functools
from typing import Optional
from redis import Redis
from global_utils.config.config import SharedConfig


@functools.lru_cache(maxsize=10)
def build_redis_client(db: Optional[int] = None) -> Redis:
    """
    Return a shared :class:`redis.Redis` for this process for the given ``db``.
    * ``db is None`` → use ``SharedConfig.get_instance().redis_db`` (backward compatible).
    * ``db=0`` and ``db=1`` (etc.) each get their **own** cached client — two logical DBs
      ⇒ two :class:`redis.Redis` instances, as intended for multi-agent.
    Tests: ``build_redis_client.cache_clear()`` to rebuild after config/mocks change.
    """
    config = SharedConfig.get_instance()
    db_index = config.redis_db if db is None else int(db)
    return Redis(
        host=config.redis_ip,
        port=int(config.redis_port),
        db=db_index,
        password=config.redis_password,
        decode_responses=config.redis_decode_responses,
    )
