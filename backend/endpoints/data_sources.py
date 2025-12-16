from flask import Blueprint, jsonify, session
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_query, from_body
from providers.data_sources import (
    get_available_data_sources,
    delete_data_source,
)
from utils.storage.mongo.mongo_helpers import get_mongo_storage

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


@data_sources_bp.route("/data.source.update", methods=["PUT"])
@from_body({
    "source_id": fields.Str(required=True),
    "updates": fields.Dict(required=True)
})
def update_source(source_id, updates):
    """
    Update a data source by its source ID.
    Updates the specified fields in the source document.
    """
    try:
        mongo_storage = get_mongo_storage()
        result = mongo_storage.update_source(source_id, updates)
        
        if result.get("success", False):
            return jsonify({
                "status": "success",
                "message": f"Source {source_id} updated successfully",
                "modified": result.get("modified", False)
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.get("message", f"Failed to update source {source_id}"),
                "error": result.get("error")
            }), 404 if "not found" in result.get("message", "").lower() else 500
            
    except Exception as e:
        logger.error(f"Failed to update data source {source_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
