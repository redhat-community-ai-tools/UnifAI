from adapters.inbound.flask.endpoints.protected_routes import protected_bp
from adapters.inbound.flask.endpoints.health import health_bp
from adapters.inbound.flask.endpoints.credentials_callback import credentials_bp
from adapters.inbound.flask.endpoints.directory_routes import directory_bp
from adapters.inbound.flask.endpoints.team_routes import team_bp
from adapters.inbound.flask.endpoints.identity_routes import identity_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": protected_bp, "parent": 'protected', "route": ''},
        {"bp": health_bp, "parent": 'health', "route": ''},
        {"bp": credentials_bp, "parent": 'credentials', "route": ''},
        {"bp": directory_bp, "parent": 'directory', "route": ''},
        {"bp": team_bp, "parent": 'teams', "route": ''},
        {"bp": identity_bp, "parent": 'identity', "route": ''},
    ]

    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")
