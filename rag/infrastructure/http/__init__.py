"""HTTP (Flask) driving adapter - REST API endpoints."""
from infrastructure.http.blueprints import register_blueprints
from infrastructure.http.health import health_bp
from infrastructure.http.vector import vector_bp
from infrastructure.http.settings import settings_bp
from infrastructure.http.pipelines import pipelines_bp
from infrastructure.http.data_sources import data_sources_bp
from infrastructure.http.docs import docs_bp
from infrastructure.http.slack import slack_bp
from infrastructure.http.terms_approval import terms_approval_bp

__all__ = [
    "register_blueprints",
    "health_bp",
    "vector_bp",
    "settings_bp",
    "pipelines_bp",
    "data_sources_bp",
    "docs_bp",
    "slack_bp",
    "terms_approval_bp",
]

