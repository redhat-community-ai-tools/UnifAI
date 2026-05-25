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
    app.secret_key = config.get("secret_key", os.urandom(24))
    app.config["admin_allowed_users"] = config.admin_allowed_users

    CORS(app, resources={r"/api/*": {"origins": "*",
                                     "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                                     "allow_headers": ["Content-Type", "Authorization",
                                                       "X-Authenticated-User"],
                                     "supports_credentials": True}})

    app.container = container
    register_all_endpoints(app)
    RequestRules(app)

    return app
