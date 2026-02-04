"""Health check endpoints - driving adapter."""
from flask import Blueprint, jsonify

from config.app_config import AppConfig

health_bp = Blueprint("health", __name__)


@health_bp.route("/", methods=["GET"])
def health_check():
    """Basic health check endpoint."""
    return jsonify({"status": "ok", "message": "Server is healthy"}), 200


@health_bp.route("/version", methods=["GET"])
def get_version():
    """Get application version."""
    config = AppConfig.get_instance()
    return jsonify({"version": config.get("version", "1.0.0")}), 200

