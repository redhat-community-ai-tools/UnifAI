from flask import Blueprint, jsonify, current_app

health_bp = Blueprint("health", __name__)

@health_bp.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Server is healthy"}), 200

@health_bp.route("/version", methods=["GET"])
def get_version():
    version = current_app.version
    return jsonify({"version": version}), 200
