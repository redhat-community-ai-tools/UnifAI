from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):
    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "0.0.0.0"
    broker_user_name: str = "guest"
    broker_password: str = "guest"

    mongodb_port: str = "27017"
    mongodb_ip: str = "0.0.0.0"

    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    qdrant_ip: str = "0.0.0.0"
    qdrant_port: str = "6333"

    # Slack Configuration
    default_slack_bot_token: str = "xoxb-2253118358-8783454711008-dwnxf7cPBpeVLlLw8KMurohb"
    default_slack_user_token: str = "xoxp-2253118358-5868044369985-8783454578416-0003b6aeff72208153bc56001e14a2dd"

    # Keycloak Configuration
    keycloak_base_url: str = "https://auth.stage.redhat.com/auth"
    client_id: str = "TAG-001"
    client_secret: str = "a0a82b17-e7e7-49c6-ad1c-3d03c79ff4fd"
    keycloak_realm: str = "EmployeeIDP"

    # Flask Configuration
    # secret_key=your-super-secret-key-change-this-in-production

    frontend_url: str = "http://localhost:5000"
    upload_folder: str = "/app/shared"
    
    # Docling Configuration
    # These will be set via environment variables in Kubernetes:
    # DOCLING_ENDPOINT_URL, DOCLING_API_VERSION, DOCLING_TIMEOUT
    docling_endpoint_url: str = "http://localhost:5001"  # Default for local dev
    docling_api_version: str = "v1alpha"
    docling_timeout: int = 300
    # session_cookie_secure=True
    backend_env: str = "development"
    version: str = "1.0.0"

    # qdrant_ip: str = "http://a467739e076d04bf1b15aa68187cbc05-1112405490.us-east-1.elb.amazonaws.com"
    # mongodb_ip: str = "ae8f0dd8e6cd046539c3f0b7c6a75f13-508991814.us-east-1.elb.amazonaws.com"
    # rabbitmq_ip: str = "a509af714a5fa4810bf879cfc8823456-1634716882.us-east-1.elb.amazonaws.com"