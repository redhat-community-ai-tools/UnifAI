from .blueprints import blueprints_bp
from .sessions import sessions_bp
from .catalog import catalog_bp
from .resources import resources_bp
from .graph import graph_bp
from .graph_validation import graph_validation_bp
from .actions import actions_bp
from .health import health_bp
from .shares import shares_bp
from .statistics import statistics_bp


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
    ]

    # register all other blueprints in the app
    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")