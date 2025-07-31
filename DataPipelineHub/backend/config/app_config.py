import os
from global_utils.config.config import SharedConfig

# Set your custom CA bundle path (required to work locally with models-corp models)
os.environ["SSL_CERT_FILE"] = "/etc/pki/tls/certs/redhat-ca.pem"

class AppConfig(SharedConfig):
    rabbitmq_port: str = "5672"
    rabbitmq_ip: str = "0.0.0.0"
    broker_user_name: str = "guest"
    broker_password: str = "guest"

    mongodb_port: str = "27017"
    mongodb_ip: str = "0.0.0.0"

    hostname: str = "0.0.0.0"
    port: str = "13456"
    
    qdrant_ip: str = "0.0.0.0"
    qdrant_port: str = "6333"
    
    # Keycloak Configuration
    keycloak_base_url: str = "https://auth.stage.redhat.com/auth"
    client_id: str = "TAG-001"
    client_secret: str = "a0a82b17-e7e7-49c6-ad1c-3d03c79ff4fd"
    keycloak_realm: str = "EmployeeIDP"
    
    # Flask Configuration
    # secret_key=your-super-secret-key-change-this-in-production
    
    frontend_url: str = "http://localhost:5000"
    # session_cookie_secure=True
    backend_env: str = "production"

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_model_base_url: str = "https://all-minilm-l6-v2--apicast-production.apps.int.stc.ai.prod.us-east-1.aws.paas.redhat.com/v1"
    embedding_model_api_key: str = "03e0e5aeb55915d0c288ebb576b240a2"
    ssl_cert_file: str = "/etc/pki/tls/certs/redhat-ca.pem"
    requests_ca_bundle: str = "/etc/pki/tls/certs/redhat-ca.pem"

    # qdrant_ip: str = "http://a467739e076d04bf1b15aa68187cbc05-1112405490.us-east-1.elb.amazonaws.com"
    # mongodb_ip: str = "ae8f0dd8e6cd046539c3f0b7c6a75f13-508991814.us-east-1.elb.amazonaws.com"
    # rabbitmq_ip: str = "a509af714a5fa4810bf879cfc8823456-1634716882.us-east-1.elb.amazonaws.com"
    
    @classmethod
    def get(cls, key: str, default=None):
        instance = cls()  # safe because of SingletonMeta
        return getattr(instance, key, default)