import logging
from typing import Callable

from flask import Blueprint, jsonify, current_app, request

from utils.directory_cache import DirectoryCache

logger = logging.getLogger(__name__)

directory_bp = Blueprint("directory", __name__)


def _parse_limit(default: int = 20) -> int:
    try:
        return int(request.args.get("limit", default))
    except (ValueError, TypeError):
        return default


def _user_token():
    return request.headers.get("X-User-Token")


def _cached_fetch(cache, cache_key: str, fetch: Callable, response_key: str, log_action: str):
    """Run fetch(), cache the result, and fall back to cache on error.

    Returns a Flask (response, status_code) tuple.
    """
    if cache:
        cached = cache.get_json(cache_key)
        if cached is not None:
            return jsonify({response_key: cached}), 200
    try:
        payload = fetch()
        if cache:
            cache.set_json(cache_key, payload)
        return jsonify({response_key: payload}), 200
    except Exception:
        logger.exception("%s failed", log_action)
        if cache:
            cached = cache.get_json(cache_key)
            if cached is not None:
                return jsonify({response_key: cached, "cached": True}), 200
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.status", methods=["GET"])
def directory_status():
    svc = current_app.extensions["team_service"]
    return jsonify({"enabled": svc.has_directory}), 200


@directory_bp.route("/directory.search_users", methods=["GET"])
def search_users():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    token = _user_token()
    cache = current_app.extensions.get("directory_cache")
    cache_key = DirectoryCache.key_for_search("users", q, limit, token)
    return _cached_fetch(
        cache, cache_key,
        fetch=lambda: [u.model_dump(mode="json") for u in svc.search_directory_users(q, limit=limit, user_token=token)],
        response_key="users",
        log_action="search_users",
    )


@directory_bp.route("/directory.search_groups", methods=["GET"])
def search_groups():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    token = _user_token()
    cache = current_app.extensions.get("directory_cache")
    cache_key = DirectoryCache.key_for_search("groups", q, limit, token)
    return _cached_fetch(
        cache, cache_key,
        fetch=lambda: [g.model_dump(mode="json") for g in svc.search_directory_groups(q, limit=limit, user_token=token)],
        response_key="groups",
        log_action="search_groups",
    )


@directory_bp.route("/directory.search", methods=["GET"])
def search_all():
    """Unified search returning both users and groups."""
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    limit = _parse_limit()
    token = _user_token()
    cache = current_app.extensions.get("directory_cache")
    users_key = DirectoryCache.key_for_search("users", q, limit, token)
    groups_key = DirectoryCache.key_for_search("groups", q, limit, token)
    users_payload = None
    groups_payload = None
    users_error = False
    groups_error = False
    try:
        users = svc.search_directory_users(q, limit=limit, user_token=token)
        users_payload = [u.model_dump(mode="json") for u in users]
        if cache:
            cache.set_json(users_key, users_payload)
    except Exception:
        logger.exception("search_all users failed")
        users_error = True
        if cache:
            users_payload = cache.get_json(users_key)

    try:
        groups = svc.search_directory_groups(q, limit=limit, user_token=token)
        groups_payload = [g.model_dump(mode="json") for g in groups]
        if cache:
            cache.set_json(groups_key, groups_payload)
    except Exception:
        logger.exception("search_all groups failed")
        groups_error = True
        if cache:
            groups_payload = cache.get_json(groups_key)

    if users_payload is None:
        users_payload = []
    if groups_payload is None:
        groups_payload = []

    if users_error and groups_error and not users_payload and not groups_payload:
        return jsonify({"error": "Internal server error"}), 500

    return jsonify({
        "users": users_payload,
        "groups": groups_payload,
        "partial": users_error or groups_error,
        "cached": (users_error and bool(users_payload)) or (groups_error and bool(groups_payload)),
    }), 200


@directory_bp.route("/directory.get_user", methods=["GET"])
def get_user():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    user_id = request.args.get("userId", "").strip()
    if not user_id:
        return jsonify({"error": "userId parameter is required"}), 400

    try:
        user = svc.get_directory_user(user_id, user_token=_user_token())
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.model_dump(mode="json")), 200
    except Exception:
        logger.exception("get_user failed")
        return jsonify({"error": "Internal server error"}), 500


@directory_bp.route("/directory.get_group", methods=["GET"])
def get_group():
    svc = current_app.extensions["team_service"]
    if not svc.has_directory:
        return jsonify({"error": "No directory provider configured"}), 501

    group_id = request.args.get("groupId", "").strip()
    if not group_id:
        return jsonify({"error": "groupId parameter is required"}), 400

    token = _user_token()
    cache = current_app.extensions.get("directory_cache")
    cache_key = DirectoryCache.key_for_group(group_id, token)

    def _fetch_group():
        group = svc.get_directory_group(group_id, user_token=token)
        if not group:
            raise KeyError(f"Group {group_id} not found")
        return group.model_dump(mode="json")

    if cache:
        cached = cache.get_json(cache_key)
        if cached is not None:
            return jsonify(cached), 200
    try:
        payload = _fetch_group()
        if cache:
            cache.set_json(cache_key, payload)
        return jsonify(payload), 200
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        logger.exception("get_group failed")
        if cache:
            cached = cache.get_json(cache_key)
            if cached is not None:
                return jsonify(cached), 200
        return jsonify({"error": "Internal server error"}), 500
