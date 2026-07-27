from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict, Callable, Optional
from .sources import DotEnvSource, YamlSource, JsonSource
from functools import lru_cache

SettingsSource = Callable[[], Dict[str, Any]]


class SharedConfig(BaseSettings):
    """
    Anything every app needs.
    """
    mongodb_port: str = "27017"
    mongodb_ip: str = "0.0.0.0"

    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "0.0.0.0"

    temporal_ip: str = "localhost"
    temporal_port: str = "7233"
    temporal_namespace: str = "default"

    redis_ip: str = "localhost"
    redis_port: str = "6379"
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_decode_responses: bool = True

    # shared loading order
    model_config = SettingsConfigDict(
        env_prefix="",
        settings_customise_sources=lambda init, env, fs: (
            init,
            env,
            DotEnvSource().load,
            YamlSource().load,
            JsonSource().load,
            fs,
        ),
    )

    @classmethod
    @lru_cache()
    def get_instance(cls):
        """Get singleton instance of this config class."""
        return cls()

    @classmethod
    def get(cls, key: str, default=None):
        """Get a config value by key."""
        instance = cls.get_instance()
        return getattr(instance, key, default)
