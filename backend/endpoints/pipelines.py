from flask import Blueprint, jsonify, session
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_body
from pipeline.pipeline_service import PipelineCeleryService
from registration.registration_service import RegistrationService

pipelines_bp = Blueprint("pipelines", __name__)


@pipelines_bp.route("/embed", methods=["PUT"])
@from_body({
    "data": fields.List(fields.Dict(), required=True),
    "source_type": fields.Str(required=True),
    "logged_in_user": fields.Str(required=True),
    "skip_validation": fields.Bool(required=False, load_default=False),
})
def start_pipeline(data, source_type, logged_in_user, skip_validation):
    """
    Trigger the embedding pipeline for registered data sources.
    Performs registration synchronously, then enqueues pipeline execution tasks to Celery.
    
    Args:
        data: List of data sources to register and process
        source_type: Type of data source (SLACK, DOCUMENT, etc.)
        logged_in_user: Username of the current user
        skip_validation: If True, skip file validation during registration.
            This should ONLY be True when files have been pre-validated via 
            the /docs/validate endpoint (UI flow).
            
            For external API calls, this should be False (default)
            to ensure full validation is performed.
            
            Note: MD5 duplicate checking is ALWAYS performed during registration
            regardless of this flag, as it requires the actual file content.
        
    Returns:
        JSON response indicating submission status
    """
    try:
        registration_response = RegistrationService().register_sources(
            data_list=data,
            source_type=source_type.upper(),
            upload_by=logged_in_user,
            skip_validation=skip_validation,
        )

        registered_sources = registration_response.get("registered_sources", [])
        if registered_sources:
            pipeline_celery_service = PipelineCeleryService()
            response_data, status_code = pipeline_celery_service.execute_pipeline(registered_sources, source_type)
        else:
            response_data, status_code = {
                "status": "no_registered_sources",
                "message": "No sources registered; skipping pipeline execution",
                "pipeline_worker_tasks_submitted": 0,
                "source_count": 0,
            }, 200

        result = {
            "registration_completed": True,
            "registration": registration_response,
            "pipeline_execution": {
                "data": response_data,
                "status_code": status_code,
            },
        }
        return jsonify(result), status_code
        
    except Exception as e:
        logger.error(f"Failed to start pipeline: {str(e)}")
        return jsonify({"error": str(e)}), 500
