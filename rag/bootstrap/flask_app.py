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
from global_utils.flask.error_handlers import register_error_handlers


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
    from global_utils.utils.logging_config import configure_logging

    configure_logging("rag-server")
    app = Flask(__name__)
    config = AppConfig.get_instance()
    
    # Application config
    if not config.secret_key:
        raise RuntimeError("secret_key is not configured. Set the SECRET_KEY environment variable.")
    app.secret_key = config.secret_key
    app.version = config.get("version", "1.0.0")
    app.config.update({
        'SESSION_COOKIE_SECURE': config.session_cookie_secure,
        'SESSION_COOKIE_HTTPONLY': config.session_cookie_http_only,
        'SESSION_COOKIE_SAMESITE': config.session_cookie_samesite,
    })
    
    # CORS
    CORS(
        app,
        supports_credentials=True,
        origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Correlation-ID"],
    )
    
    # Identity wiring — make Redis store and IdentityClient available to decorators
    from bootstrap.app_container import redis_kv_store, identity_client
    app.extensions['redis_kv_store'] = redis_kv_store()
    app.extensions['identity_client'] = identity_client()

    # Register HTTP adapters (blueprints)
    _register_blueprints(app)
    
    # Request validation rules
    RequestRules(app)
    register_error_handlers(app)
    
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

