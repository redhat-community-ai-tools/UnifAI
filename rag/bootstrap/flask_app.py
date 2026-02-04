"""
Flask Application Factory.

Creates and configures the Flask application using hexagonal architecture.
HTTP adapters are registered as blueprints.

Usage:
    from bootstrap.flask_app import create_app
    
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
"""
import os
from flask import Flask
from flask_cors import CORS

from config.app_config import AppConfig
from global_utils.flask.request_rules import RequestRules


def create_app() -> Flask:
    """
    Application factory for Flask app.
    
    Creates a Flask application with:
    - CORS configuration
    - Secret key
    - All HTTP endpoint blueprints registered
    - Request validation rules
    
    Returns:
        Configured Flask application
    """
    app = Flask(__name__)
    config = AppConfig.get_instance()
    
    # Application config
    app.secret_key = config.get("secret_key", os.urandom(24))
    app.version = config.get("version", "1.0.0")
    
    # CORS
    CORS(
        app,
        supports_credentials=True,
        origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
    )
    
    # Register HTTP adapters (blueprints)
    _register_blueprints(app)
    
    # Request validation rules
    RequestRules(app)
    
    return app


def _register_blueprints(app: Flask) -> None:
    """Register all HTTP endpoint blueprints."""
    from infrastructure.http.blueprints import register_blueprints
    register_blueprints(app)


# ══════════════════════════════════════════════════════════════════════════════
# Development Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = AppConfig.get_instance()
    application = create_app()
    application.run(
        host=config.hostname_local,
        port=config.port,
        debug=True,
    )

