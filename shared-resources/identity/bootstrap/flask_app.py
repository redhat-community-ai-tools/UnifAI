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
from global_utils.utils.logging_config import configure_logging
from bootstrap.factories import build_auth_stack, build_team_service
from global_utils.redis import TeamMembershipCache
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
    configure_logging("identity")
    config = AppConfig.get_instance()

    app = Flask(config.app_name)
        
    # Application config
    if not config.secret_key:
        raise RuntimeError("secret_key is not configured. Set the SECRET_KEY environment variable.")
    app.secret_key = config.secret_key
    app.version = config.get("version", "1.0.0")
    
    # CORS
    CORS(
        app,
        supports_credentials=True,
        origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"),
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
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

    team_membership_cache = TeamMembershipCache(redis_store)

    app.extensions['team_service'] = build_team_service(
        config,
        user_groups_cache=user_groups_cache,
        team_membership_cache=team_membership_cache,
    )
    # Register HTTP adapters (blueprints)
    _register_blueprints(app)
    
    # Request validation rules
    RequestRules(app)
    register_error_handlers(app)
    
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

