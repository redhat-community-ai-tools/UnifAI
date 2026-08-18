"""Pipeline endpoints - driving adapter."""
from flask import Blueprint, g, jsonify
from flask.wrappers import Response
from webargs import fields

from bootstrap.app_container import pipeline_dispatch_service
from global_utils.helpers.apiargs import from_body
from infrastructure.http.auth import rag_require_session
import logging

logger = logging.getLogger(__name__)

pipelines_bp = Blueprint("pipelines", __name__)


@pipelines_bp.route("/embed", methods=["PUT"])
@rag_require_session
@from_body({
    "data": fields.List(fields.Dict(), required=True),
    "source_type": fields.Str(required=True),
    "skip_validation": fields.Bool(required=False, load_default=False),
})
def start_pipeline(data: list[dict], source_type: str, skip_validation: bool) -> tuple[Response, int]:
    """
    Register sources and dispatch pipeline tasks.
    
    This endpoint:
    1. Validates and registers data sources
    2. Dispatches async pipeline tasks to Celery
    """
    try:
        result = pipeline_dispatch_service().start_pipeline(
            data=data,
            source_type=source_type,
            upload_by=g.user_id,
            skip_validation=skip_validation,
        )
        
        return jsonify(result.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Failed to start pipeline: {str(e)}")
        return jsonify({"error": str(e)}), 500

