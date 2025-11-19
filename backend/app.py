import os
import sys

# Add the parent directory of 'backend' (the root of the project) to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.storage.mongo.mongo_storage import MongoStorage
from endpoints import register_all_endpoints
from flask import Flask
from flask_cors import CORS
from global_utils.flask.request_rules import RequestRules
from config.app_config import AppConfig
from global_utils.utils.util import get_mongo_url

# from be_utils.db.flaks_db import register_mongo
# from be_utils.utils import init_flask_logger

# Init FLASK
app = Flask(__name__)

config = AppConfig.get_instance()
app.secret_key = config.get('secret_key', os.urandom(24))
app.version = config.get("version", "1.0.0")

# Configure CORS to allow credentials
CORS(app, supports_credentials=True, origins=os.environ.get("FRONTEND_URL", "http://localhost:5000"))

# init_flask_logger('access.log')
# app.config['result_backend'] = config_params.MONGODB_URL
# app.config['MONGO_URI'] = os.path.join(config_params.MONGODB_URL, config_params.MONGODB_BACKEND_COLLECTION)

# app.db = register_mongo(app)

register_all_endpoints(app)

# Init before_request/after_request rules
RequestRules(app)

if __name__ == '__main__':
    app.run(host=config.hostname_local, port=config.port, debug=True)

    # cert_file = os.path.join(os.path.dirname(__file__), 'cert.pem')
    # key_file = os.path.join(os.path.dirname(__file__), 'key.pem')

    # print(cert_file)
    # print(key_file)
    # # ✅ Enable HTTPS
    # app.run(
    #     host=hostname,
    #     port=port,
    #     debug=True,
    #     ssl_context=(cert_file, key_file)
    # )