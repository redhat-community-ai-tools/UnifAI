from api.flask.endpoints.health import health_bp
from api.flask.endpoints.admin_config import admin_config_bp
from api.flask.endpoints.slack_commands import slack_commands_bp


def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": health_bp, "parent": "health", "route": ""},
        {"bp": admin_config_bp, "parent": "admin_config", "route": ""},
        {"bp": slack_commands_bp, "parent": "slack_commands", "route": ""},
    ]

    for blueprint in backend_blueprints:
        app.register_blueprint(
            blueprint["bp"],
            url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}",
        )
