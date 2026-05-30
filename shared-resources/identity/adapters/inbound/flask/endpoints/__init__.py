from adapters.inbound.flask.endpoints.protected_routes import protected_bp
from adapters.inbound.flask.endpoints.health import health_bp
from adapters.inbound.flask.endpoints.credentials_callback import credentials_bp
from adapters.inbound.flask.endpoints.directory_routes import directory_bp
from adapters.inbound.flask.endpoints.team_routes import team_bp
from adapters.inbound.flask.endpoints.identity_routes import identity_bp
from adapters.inbound.flask.endpoints.device_auth_routes import device_auth_bp
from adapters.inbound.flask.endpoints.auth_validate_routes import auth_validate_bp
from adapters.inbound.flask.endpoints.tokens import token_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": protected_bp, "parent": 'protected', "route": ''},
        {"bp": health_bp, "parent": 'health', "route": ''},
        {"bp": credentials_bp, "parent": 'credentials', "route": ''},
        {"bp": directory_bp, "parent": 'directory', "route": ''},
        {"bp": team_bp, "parent": 'teams', "route": ''},
        {"bp": identity_bp, "parent": 'identity', "route": ''},
        {"bp": device_auth_bp, "parent": 'device-auth', "route": ''},
        {"bp": auth_validate_bp, "parent": 'auth-validate', "route": ''},
        {"bp": token_bp, "parent": 'tokens', "route": ''},
    ]

    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")
