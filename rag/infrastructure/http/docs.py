"""Document endpoints - driving adapter."""
from flask import Blueprint, jsonify
from webargs import fields

from bootstrap.app_container import (
    data_source_service,
    document_service,
    file_storage,
    file_validation_service,
    retrieval_service,
)
from global_utils.helpers.apiargs import from_query, from_body
from infrastructure.sources.document.config import DocConfigManager
from shared.logger import logger

docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/upload", methods=["POST"])
@from_body({
    "files": fields.List(fields.Dict(), required=True),
})
def upload_docs(files):
    """
    Upload document files to storage.
    
    Saves files to local storage. This endpoint receives base64-encoded files
    and stores them on disk for later processing.
    """
    try:
        storage = file_storage()
        storage.save_files(files)
        
        return jsonify({"message": "Files uploaded successfully"}), 200
        
    except Exception as e:
        logger.error(f"Failed to upload files: {str(e)}")
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/validate", methods=["POST"])
@from_body({
    "files": fields.List(fields.Dict(), required=True),
    "username": fields.Str(required=True),
    "check_duplicates": fields.Bool(required=False, load_default=True)
})
def validate_files(files, username, check_duplicates):
    """
    Validate files before upload.
    
    This endpoint performs pre-upload validation including:
    - File extension validation (must be in supported list)
    - File size validation (max 50 MB per file)
    - Duplicate name detection (allows re-upload of FAILED documents)
    
    Request body:
        files: List of file metadata objects with 'name' and 'size' keys
               Example: [{"name": "document.pdf", "size": 1024000}]
        username: Username of the person uploading files
        check_duplicates: Whether to check for duplicate filenames (default: true)
    
    Response:
        {
            "valid_files": [
                {"name": "doc.pdf", "normalized_name": "doc.pdf", "size": 1024000}
            ],
            "errors": [
                {
                    "file_name": "invalid.exe",
                    "error_type": "extension",
                    "message": "File type '.exe' is not supported..."
                }
            ],
            "has_errors": true
        }
    
    Usage Flow:
        1. UI calls this endpoint with file metadata when files are selected
        2. Backend validates and returns results
        3. UI only uploads files that passed validation
        4. UI calls /pipelines/embed with skip_validation=true
        
    For external API calls:
        - Call /pipelines/embed with skip_validation=false (default)
        - Full validation will be performed during registration
    """
    try:
        service = file_validation_service(username=username)
        result = service.validate(files, check_duplicates=check_duplicates)
        return jsonify(result.to_dict()), 200
    except Exception as e:
        logger.error(f"Failed to validate files: {str(e)}")
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/supported-extensions", methods=["GET"])
def get_supported_extensions():
    """Get list of supported document file extensions."""
    try:
        config = DocConfigManager()
        extensions = config.get_supported_file_types()
        return jsonify({"supported_extensions": extensions}), 200
    except Exception as e:
        logger.error(f"Failed to get supported extensions: {str(e)}")
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/available.docs.get", methods=["GET"])
@from_query({
    "cursor": fields.Str(required=False, load_default=""),
    "limit": fields.Int(required=False, load_default=50),
    "search_regex": fields.Str(required=False, load_default=None),
})
def get_available_docs(cursor="", limit=50, search_regex=None):
    """
    Get paginated list of available documents (DONE status only).
    Used for dropdown selection in the UI.
    """
    try:
        result = document_service().list_available_docs(
            cursor=cursor,
            limit=limit,
            search=search_regex,
        )
        return jsonify(result.to_dict(data_key="documents")), 200
        
    except Exception as e:
        logger.error(f"Failed to get available docs: {str(e)}")
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/available.tags.get", methods=["GET"])
@from_query({
    "cursor": fields.Str(required=False, load_default=""),
    "limit": fields.Int(required=False, load_default=50),
    "search_regex": fields.Str(required=False, load_default=None),
})
def get_available_tags(cursor="", limit=50, search_regex=None):
    """
    Get paginated list of available tags from DONE documents.
    Used for tag dropdown selection in the UI.
    
    Response format matches backend: options array with label/value pairs.
    """
    try:
        result = document_service().get_available_tags(
            cursor=cursor,
            limit=limit,
            search=search_regex,
        )
        
        # Format response to match backend structure
        return jsonify({
            "options": result.data,  # Already in [{label, value}] format
            "nextCursor": result.next_cursor,
            "hasMore": result.has_more,
            "total": result.total,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get available tags: {str(e)}")
        return jsonify({"error": str(e)}), 500


@docs_bp.route("/query.match", methods=["GET"])
@from_query({
    "query": fields.Str(required=True),
    "top_k_results": fields.Int(required=False, load_default=15),
    "scope": fields.Str(required=False, load_default="public"),
    "logged_in_user": fields.Str(required=False, load_default="default", data_key="loggedInUser"),
    "doc_ids": fields.List(fields.Str(), required=False, load_default=None, data_key="docIds"),
    "tags": fields.List(fields.Str(), required=False, load_default=None),
})
def query_match(query, top_k_results, scope, logged_in_user, doc_ids, tags):
    """
    Search documents using semantic similarity.
    Optionally filter by document IDs or tags.
    
    Args:
        query: Search query text
        top_k_results: Number of results to return (default: 5)
        scope: "public" or "private" - filters by upload_by if private
        logged_in_user: Username for private scope filtering
        doc_ids: Optional list of document IDs to filter by
        tags: Optional list of tags to filter by
    """
    try:
        svc = retrieval_service("DOCUMENT")
        results = svc.search(
            query=query,
            limit=top_k_results,
            scope=scope,
            user=logged_in_user,
            doc_ids=doc_ids,
            tags=tags,
        )
        
        return jsonify({"matches": results}), 200
        
    except Exception as e:
        logger.error(f"Failed to query documents: {str(e)}")
        return jsonify({"error": str(e)}), 500

