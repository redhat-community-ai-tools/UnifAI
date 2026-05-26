from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    mongo_db: str = "UnifAI"
    blueprint_coll: str = "blueprints"
    resources_coll: str = "resources"
    session_coll: str = "workflow_sessions"
    shares_coll: str = "shares"
    templates_coll: str = "templates"
    credentials_coll: str = "credentials"
    hostname: str = "0.0.0.0"
    port: str = "8002"
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access
    secret_key: str = ""
    # Engine
    engine_name: str = "temporal"
    temporal_task_queue: str = "graph-engine"
    # Redis streaming tuning
    redis_stream_ttl: int = 3600
    redis_stream_block_ms: int = 5000
    redis_stream_batch_size: int = 50

    # Collaboration hub — Redis-backed multi-user session presence ──────────
    collaboration_presence_ttl: int = 300
    collaboration_edit_lock_ttl_sec: int = 180

    # Directory provider: "sso" (via Identity pod) or "" to disable
    directory_provider: str = ""
    directory_timeout: int = 10

    # Identity HTTP base for directory + teams HTTP APIs (optional override).
    # When empty, ``identity_host`` is used for ``IdentityDirectoryClient`` and auth decorators.
    directory_sso_url: str = ""

    # MCP Auth
    mcp_auth_state_secret: str = ""
    identity_host: str = "http://localhost:13456"
    # Identity provider mode: "pod" (HTTP to Identity pod), "dev" (permissive),
    # "noop" (no teams), or "" (auto-detect from identity_host).
    identity_provider_mode: str = ""
    credential_encryption_key: str = ""
