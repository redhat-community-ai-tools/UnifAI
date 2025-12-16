from flask import Blueprint, jsonify, current_app
from global_utils.helpers.apiargs import from_query
from webargs import fields
from dataclasses import asdict

catalog_bp = Blueprint("catalog", __name__)


@catalog_bp.route("/categories.list.get", methods=["GET"])
def list_categories():
    """
    Get all available resource categories.
    Returns a list of category names.
    
    Response format:
    {
        "categories": ["llms", "tools", "retrievers", "conditions", "providers", "nodes"]
    }
    """
    try:
        catalog_service = current_app.container.catalog_service
        categories = catalog_service.list_categories()
        return jsonify({"categories": categories}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@catalog_bp.route("/elements.list.get", methods=["GET"])
def list_all_elements():
    """
    Get all elements organized by category.
    Returns category, type, and name for each element.
    
    Response format:
    {
        "elements": {
            "LLMS": [
                {"category": "LLMS", "type": "openai", "name": "OpenAI LLM"},
                {"category": "LLMS", "type": "mock", "name": "Mock LLM"}
            ],
            "NODES": [...]
        }
    }
    """
    try:
        catalog_service = current_app.container.catalog_service
        result = catalog_service.get_all_elements_summary()
        
        # Convert dataclass to dict for JSON serialization
        response = {
            "elements": {
                category: [asdict(element) for element in elements]
                for category, elements in result.elements.items()
            }
        }
        
        return jsonify(response), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@catalog_bp.route("/element.spec.get", methods=["GET"])
@from_query({
    "category": fields.Str(required=True),
    "type": fields.Str(required=True)
})
def get_element_spec(category, type):
    """
    Get detailed specification for a specific element.
    
    Query parameters:
    - category: Element category (e.g., "LLMS", "NODES") 
    - type: Element type (e.g., "openai", "custom_agent_node")
    
    Response format:
    {
        "name": "OpenAI LLM",
        "category": "LLMS", 
        "description": "Official OpenAI API configuration for LLM interactions",
        "type": "openai",
        "config_schema": {...}, // JSON schema for configuration
        "tags": ["llm", "openai", "api", "chat"]
        "output_schema": {...} // Optional output schema if available
    }
    """
    try:
        catalog_service = current_app.container.catalog_service
        result = catalog_service.get_element_detail(category, type)

        # Convert dataclass to dict for JSON serialization
        response = asdict(result)

        return jsonify(response), 200
    except KeyError as e:
        return jsonify({"error": f"Element not found: {e}"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500