"""Blueprint registration for Flask application."""
from flask import Flask

from infrastructure.http.health import health_bp
from infrastructure.http.vector import vector_bp
from infrastructure.http.settings import settings_bp
from infrastructure.http.pipelines import pipelines_bp
from infrastructure.http.data_sources import data_sources_bp
from infrastructure.http.docs import docs_bp
from infrastructure.http.slack import slack_bp
from infrastructure.http.terms_approval import terms_approval_bp


def register_blueprints(app: Flask) -> None:
    """
    Register all HTTP endpoint blueprints.
    
    URL prefixes match backend pattern: /api/{parent}/
    - /api/health/ - Health checks
    - /api/vector/ - Vector storage stats
    - /api/settings/ - Application settings
    - /api/pipelines/ - Pipeline execution
    - /api/data_sources/ - Data source management
    - /api/docs/ - Document operations
    - /api/slack/ - Slack integration
    - /api/terms_approval/ - Terms approval
    """
    app.register_blueprint(health_bp, url_prefix="/api/health/")
    app.register_blueprint(vector_bp, url_prefix="/api/vector/")
    app.register_blueprint(settings_bp, url_prefix="/api/settings/")
    app.register_blueprint(pipelines_bp, url_prefix="/api/pipelines/")
    app.register_blueprint(data_sources_bp, url_prefix="/api/data_sources/")
    app.register_blueprint(docs_bp, url_prefix="/api/docs/")
    app.register_blueprint(slack_bp, url_prefix="/api/slack/")
    app.register_blueprint(terms_approval_bp, url_prefix="/api/terms_approval/")

