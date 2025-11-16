from flask import Blueprint, jsonify
from shared.logger import logger
from providers.umami import get_website_id as _get_website_id

# we might want this as a "settings bp and not umami only"
umami_bp = Blueprint("umami", __name__)

@umami_bp.route("/get.website.id", methods=["GET"])
def get_website_id():
    """Return website ID from Umami website."""
    try:
        data = _get_website_id()
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get website ID: {e}")
        return jsonify({"error": str(e)}), 500


