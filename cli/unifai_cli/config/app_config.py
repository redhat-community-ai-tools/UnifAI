"""CLI application configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """CLI configuration — resolved from environment variables or defaults."""

    mas_url: str = "http://unifai-multiagent-be-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"
    api_prefix: str = "/api"
    sso_url: str = "https://unifai-identity-tag-ai--pipeline.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com"

    # 0 means auto-select a free port; set via AUTH_CALLBACK_PORT env var or --callback-port flag
    auth_callback_port: int = 0

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    @lru_cache()
    def get_instance(cls) -> "AppConfig":
        return cls()
