from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    mongo_db: str = "config"
    admin_config_coll: str = "admin_config"
    hostname_local: str = "0.0.0.0"
    port: str = "8005"
    version: str = "1.0.0"
    admin_allowed_users: list = []
    rag_url: str = "http://localhost:13457"
    multiagent_url: str = "http://localhost:8003"
    slack_signing_secret: str = ""
    slack_app_token: str = ""
    slack_bot_token: str = ""
    identity_host: str = "http://localhost:13456"
    secret_key: str = ""

    # Session cookie — must match Identity so Flask never re-signs with different attributes
    session_cookie_secure: bool = False
    session_cookie_http_only: bool = True
    session_cookie_samesite: str = "Lax"