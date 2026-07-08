from inbound.flask.endpoints.blueprints import blueprints_bp
from inbound.flask.endpoints.sessions import sessions_bp
from inbound.flask.endpoints.catalog import catalog_bp
from inbound.flask.endpoints.resources import resources_bp
from inbound.flask.endpoints.graph import graph_bp
from inbound.flask.endpoints.graph_validation import graph_validation_bp
from inbound.flask.endpoints.actions import actions_bp
from inbound.flask.endpoints.health import health_bp
from inbound.flask.endpoints.shares import shares_bp
from inbound.flask.endpoints.statistics import statistics_bp
from inbound.flask.endpoints.templates import templates_bp
from inbound.flask.endpoints.collaboration import collaboration_bp, collaboration_locks_bp
from inbound.flask.endpoints.workspace import workspace_bp
from inbound.flask.endpoints.credentials import credentials_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": health_bp, "parent": 'health', "route": ''},
        {"bp": blueprints_bp, "parent": 'blueprints', "route": ''},
        {"bp": sessions_bp, "parent": 'sessions', "route": ''},
        {"bp": catalog_bp, "parent": 'catalog', "route": ''},
        {"bp": resources_bp, "parent": 'resources', "route": ''},
        {"bp": graph_bp, "parent": 'graph', "route": ''},
        {"bp": graph_validation_bp, "parent": 'graph', "route": 'validation'},
        {"bp": actions_bp, "parent": 'actions', "route": ''},
        {"bp": shares_bp, "parent": 'shares', "route": ''},
        {"bp": statistics_bp, "parent": 'statistics', "route": ''},
        {"bp": templates_bp, "parent": 'templates', "route": ''},
        {"bp": collaboration_bp, "parent": 'collaboration', "route": ''},
        {"bp": collaboration_locks_bp, "parent": 'collaboration', "route": ''},
        {"bp": workspace_bp, "parent": 'workspace', "route": ''},
        {"bp": credentials_bp, "parent": 'credentials', "route": ''},
    ]

    # register all other blueprints in the app
    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")
