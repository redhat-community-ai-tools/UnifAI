from global_utils.config.config import SharedConfig
from pydantic import Field
import os


class AppConfig(SharedConfig):
    # Service discovery (internal Kubernetes DNS)
    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "rabbitmq"  # Use Kubernetes service name
    
    # Credentials from environment variables (set by Kubernetes secrets)
    broker_user_name: str = Field(default="guest", validation_alias="RABBITMQ_USER")
    broker_password: str = Field(default="guest", validation_alias="RABBITMQ_PASSWORD")

    # Database configuration  
    mongodb_port: str = "27017"
    mongodb_ip: str = "mongodb"  # Use Kubernetes service name

    # Application configuration
    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    qdrant_ip: str = "qdrant"  # Use Kubernetes service name  
    qdrant_port: str = "6333"

    # Sensitive configuration from environment variables
    # These are set via Kubernetes secrets from the private config repo
    
    # Slack Configuration - from environment
    default_slack_bot_token: str = Field(
        default="",
        validation_alias="SLACK_BOT_TOKEN",
        description="Slack bot token from Kubernetes secret"
    )
    default_slack_user_token: str = Field(
        default="", 
        validation_alias="SLACK_USER_TOKEN",
        description="Slack user token from Kubernetes secret"
    )

    # Keycloak Configuration - from environment
    keycloak_base_url: str = Field(
        default="https://auth.example.com/auth",
        validation_alias="KEYCLOAK_BASE_URL",
        description="Keycloak base URL from site configuration"
    )
    client_id: str = Field(
        default="unifai",
        validation_alias="KEYCLOAK_CLIENT_ID", 
        description="Keycloak client ID"
    )
    client_secret: str = Field(
        default="",
        validation_alias="KEYCLOAK_CLIENT_SECRET",
        description="Keycloak client secret from Kubernetes secret"
    )
    keycloak_realm: str = Field(
        default="master",
        validation_alias="KEYCLOAK_REALM",
        description="Keycloak realm name"
    )

    # Flask Configuration
    frontend_url: str = Field(
        default="http://localhost:5000",
        validation_alias="FRONTEND_URL",
        description="Frontend URL from site configuration"
    )
    upload_folder: str = "/app/shared"
    
    # Docling Configuration
    # These are set via environment variables from service discovery
    docling_endpoint_url: str = Field(
        default="http://docling-serve:5001",
        validation_alias="DOCLING_ENDPOINT_URL",
        description="Docling service endpoint from service discovery"
    )
    docling_api_version: str = "v1alpha"
    docling_timeout: int = 300
    
    # Environment detection
    backend_env: str = Field(
        default="development",
        validation_alias="BACKEND_ENV",
        description="Environment name (development/staging/production)"
    )

    # Configuration validation
    model_config = {
        "populate_by_name": True,  # Allow field names and aliases
        "env_prefix": "",  # No prefix for environment variables
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Validate required sensitive configuration in production
        if self.backend_env == "production":
            required_fields = [
                "default_slack_bot_token",
                "default_slack_user_token", 
                "client_secret"
            ]
            
            for field in required_fields:
                if not getattr(self, field):
                    raise ValueError(f"Required field {field} is not set in production environment")

    # REMOVED HARDCODED VALUES:
    # These values are now configured via environment variables from the private config repo:
    # - Slack tokens (SLACK_BOT_TOKEN, SLACK_USER_TOKEN)
    # - Keycloak client secret (KEYCLOAK_CLIENT_SECRET)  
    # - Frontend URL (FRONTEND_URL)
    # - Keycloak base URL (KEYCLOAK_BASE_URL)
    # - External service URLs (set by service discovery)
