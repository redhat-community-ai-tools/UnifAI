from flask import Blueprint, jsonify
from shared.logger import logger
from providers.vector_stats import get_chunks_counts as _get_chunks_counts

vector_bp = Blueprint("vector", __name__)

@vector_bp.route("/chunks.counts", methods=["GET"])
def get_chunks_counts():
    """Return exact chunks (points) counts for Slack and Document collections."""
    try:
        data = _get_chunks_counts()
        return jsonify(data), 200
    except Exception as e:
        logger.error(f"Failed to get chunks counts: {e}")
        return jsonify({"slack": 0, "document": 0, "total": 0, "error": str(e)}), 500


