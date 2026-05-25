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
import logging
from flask import Flask
from flask_cors import CORS

from config.app_config import AppConfig
from config.logging_config import LoggingConfig
from global_utils.flask.request_rules import RequestRules
from bootstrap.factories import build_auth_stack, build_team_service
from utils.user_groups_cache import UserGroupsCache
from utils.directory_cache import DirectoryCache


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
    
    config = AppConfig.get_instance()

    #logging setup for app and all sub-modules.
    logging.basicConfig(
        level=LoggingConfig.log_level,
        format=LoggingConfig.log_format,
    )
    logger = logging.getLogger(config.app_name)

    app = Flask(config.app_name)
        
    # Application config
    app.secret_key = config.get("secret_key", os.urandom(24)) # this key is crucial to code and decode all cookies. and it should be taken from env.
    app.version = config.get("version", "1.0.0")
    
    # CORS
    CORS(
        app,
        supports_credentials=True,
        origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
    )
    
    auth_manager, redis_store = build_auth_stack(app, config)
    app.extensions['auth_manager'] = auth_manager
    app.extensions['redis_store'] = redis_store

    user_groups_cache = UserGroupsCache(
        redis_store,
        ttl=config.user_groups_cache_ttl,
    )
    app.extensions['user_groups_cache'] = user_groups_cache
    app.extensions['directory_cache'] = DirectoryCache(
        redis_store,
        ttl_seconds=config.directory_cache_ttl,
    )

    app.extensions['team_service'] = build_team_service(config, user_groups_cache=user_groups_cache)
    # Register HTTP adapters (blueprints)
    _register_blueprints(app)
    
    # Request validation rules
    RequestRules(app)
    
    return app


def _register_blueprints(app: Flask) -> None:
    """Register all HTTP endpoint blueprints."""
    from adapters.inbound.flask.endpoints import register_all_endpoints
    register_all_endpoints(app)


app = create_app()
# ══════════════════════════════════════════════════════════════════════════════
# Development Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = AppConfig.get_instance()
    app.run(
        host=config.hostname_local,
        port=int(config.port),
        debug=True,
    )

