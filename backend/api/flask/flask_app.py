import sys
import os
from flask import Flask
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from config.app_config import AppConfig
from core.app_container import AppContainer
from .endpoints import register_all_endpoints
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules


def create_app(config: AppConfig = None) -> Flask:
    """
    Application factory.

    1) Load config
    2) Build DI container (singleton)
    3) Register Flask extensions
    4) Register API blueprints
    5) Register request rules
    """
    config = config or AppConfig.get_instance()
    app = Flask(__name__)

    # Application config
    app.version = config.get("version", "1.0.0")
    app.secret_key = config.get("secret_key", os.urandom(24))
    # CORS
    trusted_origins = [
        o.strip()
        for o in config.get("trusted_origins", os.environ.get("TRUSTED_ORIGINS", "")).split(",")
        if o.strip()
    ]
    CORS(app, resources={r"/api/*": {
        "origins": trusted_origins or ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True,
    }})

    container = AppContainer(config)
    app.container = container
    register_all_endpoints(app)
    RequestRules(app)

    return app
