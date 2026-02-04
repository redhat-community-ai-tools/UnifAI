"""Slack endpoints - driving adapter."""
from flask import Blueprint, jsonify, request
from webargs import fields

from bootstrap.app_container import (
    slack_connector,
    vector_stats_service,
    retrieval_service,
    slack_stats_service,
    slack_event_dispatch_service,
)
from global_utils.helpers.apiargs import from_query
from shared.logger import logger

slack_bp = Blueprint("slack", __name__)

# Default project ID - should come from session/config in production
DEFAULT_PROJECT_ID = "default"


@slack_bp.route("/fetch.available.slack.channels", methods=["PUT"])
def fetch_slack_channels():
    """Fetch and cache Slack channels from the API."""
    try:
        connector = slack_connector(DEFAULT_PROJECT_ID)
        channels = connector.fetch_and_cache_channels()
        return jsonify({"status": "channels fetched and cached", "count": len(channels)}), 200
    except Exception as e:
        logger.error(f"Failed to fetch available Slack channels: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/available.slack.channels.get", methods=["GET"])
@from_query({
    "types": fields.Str(required=True, data_key="types"),
    "cursor": fields.Str(required=False, load_default="", data_key="cursor"),
    "limit": fields.Int(required=False, load_default=50, data_key="limit"),
    "search_regex": fields.Str(required=False, load_default=None, data_key="search_regex"),
})
def get_available_channels(types, cursor, limit, search_regex):
    """
    Get cached Slack channels with pagination.
    
    Args:
        types: Channel types filter (e.g., "public_channel,private_channel") - required
        cursor: Pagination cursor
        limit: Max channels to return
        search_regex: Search pattern for channel names
    """
    try:
        connector = slack_connector(DEFAULT_PROJECT_ID)
        result = connector.get_available_slack_channels_from_cache(
            types=types,
            cursor=cursor if cursor else None,
            limit=limit,
            search_regex=search_regex,
        )
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Failed to get available Slack channels: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/slack.channel.chunks", methods=["GET"])
@from_query({"channel_name": fields.Str(required=True)})
def get_channel_chunks(channel_name):
    """Get chunk count for a specific Slack channel."""
    try:
        count = vector_stats_service().count_by_filter(
            collection_name="slack_data",
            filters={"metadata.channel_name": channel_name},
        )
        return jsonify({
            "channel_name": channel_name,
            "chunk_count": count,
        }), 200
        
    except Exception as e:
        logger.error(f"Counting chunks failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/user.info.get", methods=["GET"])
@from_query({
    "user_id": fields.Str(required=False, load_default=None, data_key="user_id"),
    "include_locale": fields.Bool(required=False, load_default=False, data_key="include_locale"),
})
def get_user_info(user_id, include_locale):
    """
    Get user information from Slack using the users.info API.
    
    Args:
        user_id: Optional user ID to get info for. If not provided, gets info for current authenticated user.
        include_locale: Whether to include locale information in the response.
    
    Returns:
        JSON response containing user information from Slack
    """
    try:
        connector = slack_connector(DEFAULT_PROJECT_ID)
        user_info = connector.get_user_info(user_id=user_id, include_locale=include_locale)
        
        return jsonify({"status": "success", "user_info": user_info}), 200
            
    except Exception as e:
        logger.error(f"Failed to get Slack user info: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/query.match", methods=["GET"])
@from_query({
    "query": fields.Str(required=True),
    "top_k_results": fields.Int(required=False, load_default=5),
    "scope": fields.Str(required=False, load_default="public"),
    "logged_in_user": fields.Str(required=False, load_default="default", data_key="loggedInUser"),
})
def query_match(query, top_k_results, scope, logged_in_user):
    """Search Slack messages using semantic similarity."""
    try:
        svc = retrieval_service("SLACK")
        results = svc.search(
            query=query,
            limit=top_k_results,
            scope=scope,
            user=logged_in_user,
        )
        
        return jsonify({"search_results": results}), 200
        
    except Exception as e:
        logger.error(f"Failed to query Slack messages: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/stats", methods=["GET"])
def slack_stats():
    """Get aggregated Slack statistics."""
    try:
        stats = slack_stats_service().get_stats()
        return jsonify(stats.to_dict()), 200
    except Exception as e:
        logger.error(f"Failed to get Slack stats: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/events", methods=["POST"])
def slack_events():
    """
    Handle Slack Events API webhooks.
    
    Handles:
    - URL verification challenge
    - Event callbacks (dispatched to Celery)
    """
    try:
        payload = request.get_json()
        result = slack_event_dispatch_service().handle_webhook(payload)
        
        # URL verification returns the challenge directly
        if result.event_type == "url_verification":
            return result.message, 200
            
        return jsonify({
            "status": "ok",
            "message": result.message,
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to handle Slack event: {str(e)}")
        return jsonify({"error": str(e)}), 500

