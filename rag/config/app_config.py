"""Application configuration for RAG service."""

from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    """RAG application configuration."""
    
    # RabbitMQ Configuration
    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "0.0.0.0"
    broker_user_name: str = "guest"
    broker_password: str = "guest"

    # MongoDB Configuration
    mongodb_port: str = "27017"
    mongodb_ip: str = "0.0.0.0"

    # Server Configuration
    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    # Qdrant Configuration
    qdrant_ip: str = "0.0.0.0"
    qdrant_port: str = "6333"
    
    # Slack Configuration
    default_slack_bot_token: str = ""
    default_slack_user_token: str = ""

    # Flask Configuration
    frontend_url: str = "http://localhost:5000"
    upload_folder: str = "/app/shared"
    backend_env: str = "development"
    version: str = "1.0.0"
    secret_key: str = ""
    identity_host: str = "http://localhost:13456"

    # Session cookie — must match Identity so Flask never re-signs with different attributes
    session_cookie_secure: bool = False
    session_cookie_http_only: bool = True
    session_cookie_samesite: str = "Lax"

    # Umami Configuration
    umami_url: str = "0.0.0.0"
    umami_website_name: str = "unifai"
    umami_username: str = "dummy"
    umami_password: str = "dummy"

    # External Docling Service Configuration
    docling_service_url: str = "http://docling-service:5001"
    docling_service_timeout: int = 300
    docling_poll_interval: int = 10
    docling_http_timeout: int = 60
    docling_pdf_backend: str = "dlparse_v4"

    # External Embedding Service Configuration
    embedding_service_url: str = "http://embedding-service:5002"
    embedding_service_timeout: int = 60
    embedding_service_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Feature flags to switch between local and remote adapters
    use_remote_docling: bool = False
    use_remote_embedding: bool = False
