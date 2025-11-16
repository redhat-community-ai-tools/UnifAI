from flask import Blueprint, jsonify, session, request
from providers.slack.stats import SlackStatsProvider
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from webargs import fields
from shared.logger import logger
from global_utils.helpers.apiargs import from_query, from_body
from global_utils.celery_app.helpers import send_task
from global_utils.celery_app import CeleryApp
from config.constants import DataSource
from providers.slack.slack import (
     count_channel_chunks,
    get_available_slack_channels,
    get_best_match_results,
    fetch_available_slack_channels,
    get_slack_user_info,
)
import requests
slack_bp = Blueprint("slack", __name__)

@slack_bp.route("/fetch.available.slack.channels", methods=["PUT"])
def fetch_slack_channels():
    try:
        channels = fetch_available_slack_channels()
        return jsonify({"status": "channels fetched and cached", "count": len(channels)}), 200
    except Exception as e:
        logger.error(f"Failed to fetch available Slack channels: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/available.slack.channels.get", methods=["GET"])
@from_query({
    "types": fields.Str(required=True, data_key='types'),
    "cursor": fields.Str(required=False, data_key='cursor', load_default=""),
    "limit": fields.Int(required=False, data_key='limit', load_default=50),
    "search_regex": fields.Str(required=False, data_key='search_regex', load_default=None)
})
def available_slack_channels(types, cursor="", limit=50, search_regex=None):
    try:
        result = get_available_slack_channels(types, cursor=cursor, limit=limit, search_regex=search_regex)
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Failed to get available Slack channels: {str(e)}")
        return jsonify({"error": str(e)}), 500


# @slack_bp.route("/embed.channels.direct", methods=["PUT"])
# @from_body({
#     "channels": fields.List(fields.Dict(), required=True)
# })
# def embed_channels(channels):
#     try:
#         results = embed_slack_channels_flow(channels)
#         return jsonify({"status": "success", "details": results}), 200
#     except Exception as e:
#         logger.error(f"Embedding Slack channels failed: {str(e)}")
#         return jsonify({"error": str(e)}), 500


@slack_bp.route("/slack.channel.chunks", methods=["GET"])
@from_query({
    "channel_name": fields.Str(required=True)
})
def slack_channel_chunks(channel_name):
    try:
        count = count_channel_chunks(channel_name)
        return jsonify({"channel_name": channel_name, "chunk_count": count}), 200
    except Exception as e:
        logger.error(f"Counting chunks failed: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/user.info.get", methods=["GET"])
@from_query({
    "user_id": fields.Str(required=False, data_key='user_id', load_default=None),
    "include_locale": fields.Bool(required=False, data_key='include_locale', load_default=False)
})
def slack_user_info(user_id, include_locale):
    """
    Get user information from Slack using the users.info API.
    
    Args:
        user_id: Optional user ID to get info for. If not provided, gets info for current authenticated user.
        include_locale: Whether to include locale information in the response.
    
    Returns:
        JSON response containing user information from Slack
    """
    try:
        user_info = get_slack_user_info(user_id=user_id, include_locale=include_locale)
        return jsonify({"status": "success", "user_info": user_info}), 200
    except Exception as e:
        logger.error(f"Failed to get Slack user info: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
    
@slack_bp.route("/query.match", methods=["GET"])
@from_query({
    "query": fields.Str(required=True),
    "top_k_results": fields.Int(required=False),
    "scope": fields.Str(required=False, load_default="public"),
    "logged_in_user": fields.Str(required=False, load_default="default", data_key="loggedInUser")
})
def best_match_results(query, top_k_results, scope, logged_in_user):
    try:
        search_results = get_best_match_results(query, top_k_results, scope, logged_in_user)
        return jsonify({"search_results": search_results}), 200
    except Exception as e:
        logger.error(f"Failed to find best match for user query: {str(e)}")
        return jsonify({"error": str(e)}), 500


@slack_bp.route("/stats", methods=["GET"])
def slack_stats():
    """
    Get Slack statistics including channel counts, message totals, and sync information.
    
    Returns:
        JSON response containing Slack statistics
    """
    try:
        stats_provider = SlackStatsProvider()
        stats = stats_provider.get_stats()
        
        # Convert dataclass to dict for JSON serialization
        stats_dict = {
            "id": stats.id,
            "totalChannels": stats.totalChannels,
            "activeChannels": stats.activeChannels,
            "totalMessages": stats.totalMessages,
            "apiCallsCount": stats.apiCallsCount,
            "lastSyncAt": stats.lastSyncAt,
            "totalEmbeddings": stats.totalEmbeddings,
            "updatedAt": stats.updatedAt
        }
        
        return jsonify(stats_dict), 200
    except Exception as e:
        logger.error(f"Failed to get Slack stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@slack_bp.route("/events", methods=["POST"])
def slack_events():
    """
    Slack Events API endpoint.
    Handles URL verification and enqueues events to Celery.
    """
    try:
        payload = request.get_json()
    except Exception as e:
        logger.error(f"Failed to parse Slack event JSON: {e}")
        return jsonify({"error": "Invalid JSON"}), 400
    
    # this check is only a helath check for the coneciton between slack and this endpoint
    if payload.get('type') == 'url_verification':
        challenge = payload.get('challenge', '')
        logger.info(f"Slack URL verification challenge received")
        return jsonify({"challenge": challenge}), 200
    
    # this is the main endpoint for the slack events
    if payload.get('type') == 'event_callback':
        try:
            send_task(
                task_name="celery_app.tasks.slack_event_subscription_tasks.process_slack_events_task",
                celery_queue="slack_events_queue",
                payload=payload,
            )
            logger.info(f"Enqueued Slack event {payload.get('event_id')} to Celery")
        except Exception as e:
            logger.error(f"Failed to enqueue Slack event to Celery: {e}")
    
    return jsonify({"status": "ok"}), 200
