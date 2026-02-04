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

    # Umami Configuration
    umami_url: str = "0.0.0.0"
    umami_website_name: str = "unifai"
    umami_username: str = "dummy"
    umami_password: str = "dummy"

