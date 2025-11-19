from endpoints.slack import slack_bp
from endpoints.pipelines import pipelines_bp
from endpoints.docs import docs_bp
from endpoints.health import health_bp
from endpoints.data_sources import data_sources_bp
from endpoints.vector import vector_bp

def register_all_endpoints(app):
    backend_blueprints = [
        {"bp": health_bp, "parent": 'health', "route": ''},
        {"bp": pipelines_bp, "parent": 'pipelines', "route": ''},
        {"bp": slack_bp, "parent": 'slack', "route": ''},
        {"bp": docs_bp, "parent": 'docs', "route": ''},
        {"bp": data_sources_bp, "parent": 'data_sources', "route": ''},
        {"bp": vector_bp, "parent": 'vector', "route": ''},
    ]
    
    # register all other blueprints in the app
    for blueprint in backend_blueprints:
        app.register_blueprint(blueprint["bp"], url_prefix=f"/api/{blueprint['parent']}/{blueprint['route']}")
