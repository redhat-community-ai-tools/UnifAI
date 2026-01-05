from flask import Blueprint, jsonify, session
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_query, from_body
from providers.data_sources import (
    get_available_data_sources,
    delete_data_source,
    get_data_source_details,
)
from utils.storage.mongo.mongo_helpers import get_mongo_storage

data_sources_bp = Blueprint("data_sources", __name__)

@data_sources_bp.route("/data.sources.get", methods=["GET"])
@from_query({
    "source_type": fields.Str(required=True),
    "filter_query": fields.Str(required=False, load_default=None)
})
def available_data_sources(source_type, filter_query):
    try:
        sources = get_available_data_sources(source_type=source_type, filter_query=filter_query)
        return jsonify({"sources": sources}), 200

    except Exception as e:
        logger.error(f"Failed to get available data sources list: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

@data_sources_bp.route("/data.source.delete", methods=["DELETE"])
@from_body({"pipeline_ids": fields.List(fields.Str(), required=True)})
def delete_source(pipeline_ids):
    """
    Delete one or more data sources by their pipeline IDs.
    Removes the sources from both MongoDB and vector storage.
    Accepts a list of pipeline_ids - for single deletion, pass a 1-element list.
    """
    try:
        results = {
            "succeeded": [],
            "failed": []
        }
        
        for pipeline_id in pipeline_ids:
            try:
                result = delete_data_source(pipeline_id)
                if result.get("success", False):
                    results["succeeded"].append({
                        "pipeline_id": pipeline_id,
                        "result": result.get("result", {})
                    })
                else:
                    results["failed"].append({
                        "pipeline_id": pipeline_id,
                        "error": result.get("message", "Unknown error")
                    })
            except Exception as e:
                results["failed"].append({
                    "pipeline_id": pipeline_id,
                    "error": str(e)
                })
        
        if len(results["failed"]) == 0:
            return jsonify({
                "status": "success",
                "message": f"Successfully deleted {len(results['succeeded'])} source(s)",
                "results": results
            }), 200
        elif len(results["succeeded"]) > 0:
            return jsonify({
                "status": "partial",
                "message": f"Deleted {len(results['succeeded'])} source(s), {len(results['failed'])} failed",
                "results": results
            }), 207  # Multi-Status
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to delete all {len(results['failed'])} source(s)",
                "results": results
            }), 500
            
    except Exception as e:
        logger.error(f"Failed to delete data sources: {str(e)}")
        return jsonify({"error": str(e)}), 500

@data_sources_bp.route("/data.source.details.get", methods=["GET"])
@from_query({"source_id": fields.Str(required=True)})
def get_source_details(source_id):
    """
    Get detailed information for a single data source, including full text.
    This endpoint is used for lazy loading expanded row data.
    """
    try:
        result = get_data_source_details(source_id)

        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify({
                "success": False,
                "message": result.get("message", f"Source {source_id} not found")
            }), 404

    except Exception as e:
        logger.error(f"Failed to get data source details for {source_id}: {str(e)}")
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
