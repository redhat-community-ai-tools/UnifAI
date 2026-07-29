"""
Device Authorization Grant (RFC 8628) endpoints for CLI/programmatic access.

Allows API clients to authenticate via SSO without a browser on the same machine.
The flow:
  1. Client calls POST /authorize → gets user_code + verification URL
  2. User opens URL in any browser, enters code, logs in via Keycloak
  3. Client polls POST /token until login completes → gets session_id

The session_id can then be used as Authorization: Bearer <session_id> on all
protected API endpoints.
"""
import logging
import uuid
from datetime import datetime, timedelta

import requests as http_requests
from flask import Blueprint, current_app, jsonify, request

from config.app_config import AppConfig
from global_utils.redis.constants import identity_session_key

logger = logging.getLogger(__name__)
config = AppConfig.get_instance()

device_auth_bp = Blueprint("device_auth", __name__)

_DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


def _keycloak_device_endpoint() -> str:
    base = config.keycloak_base_url.rstrip("/")
    realm = config.keycloak_realm
    return f"{base}/realms/{realm}/protocol/openid-connect/auth/device"


def _keycloak_token_endpoint() -> str:
    base = config.keycloak_base_url.rstrip("/")
    realm = config.keycloak_realm
    return f"{base}/realms/{realm}/protocol/openid-connect/token"


@device_auth_bp.route("/authorize", methods=["POST"])
def device_authorize():
    """Start the Device Authorization flow.

    Calls Keycloak's device_authorization_endpoint and returns the user_code
    and verification URL to the caller.
    """
    try:
        resp = http_requests.post(
            _keycloak_device_endpoint(),
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "scope": "openid email profile",
            },
            timeout=10,
        )

        if resp.status_code != 200:
            logger.error("Keycloak device auth failed: %s %s", resp.status_code, resp.text)
            return jsonify({"error": "Failed to initiate device authorization"}), 502

        data = resp.json()
        return jsonify({
            "device_code": data["device_code"],
            "user_code": data["user_code"],
            "verification_uri": data["verification_uri"],
            "verification_uri_complete": data.get("verification_uri_complete", ""),
            "expires_in": data.get("expires_in", 600),
            "interval": data.get("interval", 5),
        }), 200

    except http_requests.RequestException as e:
        logger.exception("Network error contacting Keycloak device endpoint")
        return jsonify({"error": "Unable to reach authentication server"}), 502


@device_auth_bp.route("/token", methods=["POST"])
def device_token():
    """Poll for token after user completes login.

    The client calls this repeatedly (respecting the ``interval``) until
    the user finishes the browser login flow.

    On success, creates a Redis session (identical to a UI login session)
    and returns the session_id for use as a Bearer token.
    """
    body = request.get_json(silent=True) or {}
    device_code = body.get("device_code", "").strip()

    if not device_code:
        return jsonify({"error": "device_code is required"}), 400

    try:
        resp = http_requests.post(
            _keycloak_token_endpoint(),
            data={
                "grant_type": _DEVICE_GRANT_TYPE,
                "device_code": device_code,
                "client_id": config.client_id,
                "client_secret": config.client_secret,
            },
            timeout=10,
        )

        data = resp.json()

        if resp.status_code != 200:
            error_code = data.get("error", "")
            if error_code == "authorization_pending":
                return jsonify({"status": "authorization_pending"}), 200
            if error_code == "slow_down":
                return jsonify({"status": "slow_down"}), 200
            if error_code == "expired_token":
                return jsonify({"error": "Device code expired. Please restart the login flow."}), 410

            logger.error("Keycloak token exchange failed: %s", data)
            return jsonify({"error": data.get("error_description", "Token exchange failed")}), 400

        # Success — extract user info from the access token
        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        token_expires_at = data.get("expires_at", 0)

        userinfo = _fetch_userinfo(access_token)
        if not userinfo:
            return jsonify({"error": "Failed to fetch user info"}), 500

        # Create a Redis session (same format as UI login)
        session_id = str(uuid.uuid4())
        session_created_at = datetime.now()
        session_expires_at = session_created_at + timedelta(hours=config.permanent_session_lifetime)
        ttl_seconds = max(0, int(session_expires_at.timestamp() - session_created_at.timestamp()))

        session_data = {
            "username": userinfo.get("preferred_username", ""),
            "email": userinfo.get("email", ""),
            "name": userinfo.get("name", ""),
            "sub": userinfo.get("sub", ""),
            "session_created_at": session_created_at.timestamp(),
            "session_expires_at": session_expires_at.timestamp(),
            "token_expires_at": token_expires_at or data.get("expires_in", 0),
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

        auth_manager = current_app.extensions.get("auth_manager")
        auth_manager.redis_store.hset(
            identity_session_key(session_id), session_data, ttl_seconds=ttl_seconds
        )

        return jsonify({
            "session_id": session_id,
            "username": userinfo.get("preferred_username", ""),
            "expires_in": ttl_seconds,
        }), 200

    except http_requests.RequestException as e:
        logger.exception("Network error during device token exchange")
        return jsonify({"error": "Unable to reach authentication server"}), 502


def _fetch_userinfo(access_token: str) -> dict | None:
    """Fetch user info from Keycloak using the access token."""
    base = config.keycloak_base_url.rstrip("/")
    realm = config.keycloak_realm
    url = f"{base}/realms/{realm}/protocol/openid-connect/userinfo"

    try:
        resp = http_requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error("Userinfo fetch failed: %s", resp.status_code)
        return None
    except http_requests.RequestException:
        logger.exception("Network error fetching userinfo")
        return None
