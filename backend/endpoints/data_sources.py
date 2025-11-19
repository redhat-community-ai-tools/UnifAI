from flask import Blueprint, jsonify, session
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_query, from_body
from providers.data_sources import (
    get_available_data_sources,
    delete_data_source,
)
data_sources_bp = Blueprint("data_sources", __name__)

@data_sources_bp.route("/data.sources.get", methods=["GET"])
@from_query({"source_type": fields.Str(required=True)})
def available_data_sources(source_type):
    try:
        sources = get_available_data_sources(source_type=source_type)
        return jsonify({"sources": sources}), 200

    except Exception as e:
        logger.error(f"Failed to get available data sources list: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

@data_sources_bp.route("/data.source.delete", methods=["DELETE"])
@from_body({"pipeline_id": fields.Str(required=True)})
def delete_source(pipeline_id):
    """
    Delete a data source by its pipeline ID.
    Removes the source from both MongoDB and vector storage.
    """
    try:
        result = delete_data_source(pipeline_id)
        
        if result.get("success", False):
            return jsonify({
                "status": "success", 
                "message": f"Source {pipeline_id} deleted successfully", 
                "result": result.get("result", {})
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to delete source {pipeline_id}",
                "result": result.get("result", {})
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to delete data source {pipeline_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
