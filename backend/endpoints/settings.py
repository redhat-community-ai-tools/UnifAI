from flask import Blueprint, jsonify
from shared.logger import logger
from providers.settings import get_umami_settings as _get_umami_settings

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/get.umami.settings", methods=["GET"])
def get_umami_settings():
    """Return website ID from Umami website."""
    try:
        data = _get_umami_settings()
        return jsonify(data), 200
    except ValueError as e:
        # Configuration issue (e.g., website not found)
        logger.error(f"Umami configuration error: {e}")
        return jsonify({"error": "Website ID not found in Umami"}), 500
    except ConnectionError as e:
        # Network/connection issue
        logger.error(f"Failed to connect to Umami service: {e}")
        return jsonify({"error": "Umami service unavailable"}), 503
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error getting Umami settings: {e}")
        return jsonify({"error": "Internal server error"}), 500

