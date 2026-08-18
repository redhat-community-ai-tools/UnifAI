import sys
import os
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.app_config import AppConfig
from core.app_container import AppContainer
from .endpoints import register_all_endpoints
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from global_utils.flask.error_handlers import register_error_handlers


def create_app(config: AppConfig = None) -> Flask:
    """
    Application factory.

    1) Load config
    2) Build DI container (singleton)
    3) Register Flask extensions
    4) Register API blueprints
    5) Register request rules
    """
    from global_utils.utils.logging_config import configure_logging

    configure_logging("backend")
    config = config or AppConfig.get_instance()
    app = Flask(__name__)

    # Application config
    app.version = config.get("version", "1.0.0")
    if not config.secret_key:
        raise RuntimeError("secret_key is not configured. Set the SECRET_KEY environment variable.")
    app.secret_key = config.secret_key
    app.config.update({
        'SESSION_COOKIE_SECURE': config.session_cookie_secure,
        'SESSION_COOKIE_HTTPONLY': config.session_cookie_http_only,
        'SESSION_COOKIE_SAMESITE': config.session_cookie_samesite,
    })
    # CORS
    CORS(app, resources={r"/api/*": {
        "origins": os.environ.get("FRONTEND_URL", "http://localhost:5000"),
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Request-ID", "X-Correlation-ID"],
        "supports_credentials": True,
    }})

    container = AppContainer(config)
    app.container = container
    register_all_endpoints(app)
    RequestRules(app)
    register_error_handlers(app)

    return app
