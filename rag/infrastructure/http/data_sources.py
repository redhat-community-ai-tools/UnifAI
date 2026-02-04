"""Data source endpoints - driving adapter."""
from flask import Blueprint, jsonify
from webargs import fields

from bootstrap.app_container import data_source_service
from global_utils.helpers.apiargs import from_query, from_body
from shared.logger import logger

data_sources_bp = Blueprint("data_sources", __name__)


@data_sources_bp.route("/data.sources.get", methods=["GET"])
@from_query({
    "source_type": fields.Str(required=True),
    "include_full_details": fields.Bool(required=False, load_default=False),
})
def get_sources(source_type, include_full_details):
    """Get all data sources with pipeline stats for a given type.
    
    Args:
        source_type: Type of data source (e.g., "DOCUMENT", "SLACK")
        include_full_details: If False (default), excludes heavy fields like 
                              full_text for better list performance. If True,
                              returns complete data.
    """
    try:
        sources = data_source_service().list_with_stats(
            source_type,
            include_full_details=include_full_details,
        )
        return jsonify({"sources": sources}), 200
    except Exception as e:
        logger.error(f"Failed to get available data sources list: {str(e)}")
        return jsonify({"error": str(e)}), 500


@data_sources_bp.route("/data.source.delete", methods=["DELETE"])
@from_body({"pipeline_ids": fields.List(fields.Str(), required=True)})
def delete_sources(pipeline_ids):
    """
    Delete one or more data sources by their source IDs.
    Removes the sources from both MongoDB and vector storage.
    
    Note: Parameter is named 'pipeline_ids' for API compatibility, but actually
    uses source_id for lookup (matching backend behavior).
    """
    try:
        svc = data_source_service()
        results = {"succeeded": [], "failed": []}
        
        for source_id in pipeline_ids:
            try:
                # Get source by source_id (matching backend behavior)
                source = svc.get_by_id(source_id)
                if not source:
                    results["failed"].append({
                        "pipeline_id": source_id,
                        "error": "Source not found"
                    })
                    continue
                
                result = svc.delete(source.source_id)
                if result.success:
                    results["succeeded"].append({
                        "pipeline_id": source_id,
                        "result": {
                            "source_id": result.source_id,
                            "source_name": result.source_name,
                            "qdrant_embeddings_deleted": result.vectors_deleted,
                            "mongo_source_deleted": result.source_deleted,
                            "mongo_pipelines_deleted": result.pipelines_deleted,
                        }
                    })
                else:
                    results["failed"].append({
                        "pipeline_id": source_id,
                        "error": result.message
                    })
            except Exception as e:
                results["failed"].append({
                    "pipeline_id": source_id,
                    "error": str(e)
                })
        
        # Format response based on results
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
        result = data_source_service().get_with_stats(source_id)
        
        if result:
            return jsonify({"success": True, "source": result}), 200
        else:
            return jsonify({
                "success": False,
                "message": f"Source {source_id} not found"
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
    """Update a data source by its source ID."""
    try:
        success = data_source_service().update(source_id, updates)
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Source {source_id} updated successfully",
                "modified": True
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": f"Source {source_id} not found"
            }), 404
            
    except Exception as e:
        logger.error(f"Failed to update data source {source_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500

