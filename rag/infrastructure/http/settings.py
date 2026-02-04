"""Settings endpoints - driving adapter."""
from flask import Blueprint, jsonify

from bootstrap.app_container import umami_client
from config.app_config import AppConfig
from shared.logger import logger

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/get.umami.settings", methods=["GET"])
def get_umami_settings():
    """Get Umami analytics settings for the frontend."""
    try:
        config = AppConfig.get_instance()
        website_name = config.get("umami_website_name", "unifai")
        data = umami_client().get_website_id(website_name)
        return jsonify(data), 200
    except ValueError as e:
        logger.error(f"Umami configuration error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        logger.error(f"Umami service unavailable: {e}")
        return jsonify({"error": "Umami service unavailable"}), 503

