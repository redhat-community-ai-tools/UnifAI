from global_utils.config.config import SharedConfig


class AppConfig(SharedConfig):

    hostname_local: str = "0.0.0.0"
    port: str = "13456"

    # Keycloak Configuration
    keycloak_base_url: str = "https://auth.stage.redhat.com/auth"
    client_id: str = "TAG-001"
    client_secret: str = "a0a82b17-e7e7-49c6-ad1c-3d03c79ff4fd"
    keycloak_realm: str = "EmployeeIDP"
    version: str = "1.0.0"


    frontend_url: str = "http://localhost:5000"    # session_cookie_secure=True
    backend_env: str = "development"

