from flask import Flask
from config.app_config import AppConfig
from .endpoints import register_all_endpoints
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
import os


def create_app(container, config: AppConfig = None) -> Flask:
    """
    Application factory.

    Receives a fully-wired AppContainer from the entry point.
    This adapter never creates the container itself — it only consumes it.
    """
    config = config or AppConfig.get_instance()
    app = Flask(__name__)
    app.version = config.get("version", "1.0.0")
    if not config.secret_key:
        raise RuntimeError("secret_key is not configured. Set the SECRET_KEY environment variable.")
    app.secret_key = config.secret_key
    app.config["admin_allowed_users"] = config.admin_allowed_users
    app.config.update({
        'SESSION_COOKIE_SECURE': config.session_cookie_secure,
        'SESSION_COOKIE_HTTPONLY': config.session_cookie_http_only,
        'SESSION_COOKIE_SAMESITE': config.session_cookie_samesite,
    })

    CORS(app, resources={r"/api/*": {
        "origins": os.environ.get("FRONTEND_URL", "http://localhost:5000"),
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
    }})

    app.container = container
    register_all_endpoints(app)
    RequestRules(app)

    return app
