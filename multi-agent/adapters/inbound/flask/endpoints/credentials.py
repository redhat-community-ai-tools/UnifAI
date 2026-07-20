"""
Flask endpoints for the credentials lifecycle.

Routes:
  POST /api/credentials/exchange            — Exchange auth code for tokens (OAuth callback)
  GET  /api/credentials/status              — Check token status for the authenticated user
  POST /api/credentials/client-config.save  — Save OAuth client credentials for an auth server
  GET  /api/credentials/client-config.get   — Get OAuth client config for an auth server
"""

import logging

from flask import Blueprint, jsonify, g, current_app
from global_utils.helpers.apiargs import from_body, from_query
from global_utils.utils.async_bridge import get_async_bridge
from inbound.flask.decorators import (
    require_admin_access,
    require_session_identity,
    G_IDENTITY_USERNAME,
)
from mas.core.auth.credentials.models import ClientConfig
from webargs import fields

logger = logging.getLogger(__name__)

credentials_bp = Blueprint("credentials", __name__)


@credentials_bp.route("/exchange", methods=["POST"])
@from_body({
    "code": fields.Str(required=True),
    "state": fields.Str(required=True),
})
def exchange_code(code, state):
    """
    Exchange an authorization code for tokens.

    Called by the SSO pod after receiving the OAuth callback.
    Delegates to AuthService.complete() which handles state validation,
    pending-flow consumption, and token persistence.
    """
    try:
        auth_service = current_app.container.auth_service
        with get_async_bridge() as bridge:
            result = bridge.run(auth_service.complete({"code": code, "state": state}))
        return jsonify(result), 200
    except Exception as e:
        logger.exception("Token exchange failed")
        return jsonify({"error": "Token exchange failed"}), 400


@credentials_bp.route("/status", methods=["GET"])
@require_session_identity
@from_query({
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
})
def token_status(identity, server_identifier):
    """Check whether the authenticated user has a valid credential for an auth server."""
    try:
        user_id = getattr(g, G_IDENTITY_USERNAME, "") or ""
        if not user_id:
            return jsonify({
                "error": "Access denied: user identification is required",
                "error_type": "AUTHENTICATION_REQUIRED",
            }), 401

        store = current_app.container.credential_store
        cred = store.find_by_server(user_id=user_id, server_identifier=server_identifier)
        if cred and cred.is_valid():
            return jsonify({
                "authenticated": True,
                "status": "active",
                "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
            }), 200
        return jsonify({
            "authenticated": False,
            "status": "expired" if cred else "not_found",
        }), 200
    except Exception as e:
        logger.exception("Token status check failed")
        return jsonify({"error": "Status check failed"}), 400


@credentials_bp.route("/client-config.save", methods=["POST"])
@require_admin_access
@from_body({
    "client_id": fields.Str(data_key="clientId", required=True),
    "client_secret": fields.Str(data_key="clientSecret", required=False, load_default=None),
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
    "display_name": fields.Str(data_key="displayName", required=False, load_default=""),
    "categories": fields.List(fields.Str(), required=False, load_default=list),
    "authorization_endpoint": fields.Str(data_key="authorizationEndpoint", required=False, load_default=""),
    "token_endpoint": fields.Str(data_key="tokenEndpoint", required=False, load_default=""),
    "token_endpoint_auth_method": fields.Str(data_key="tokenEndpointAuthMethod", required=False, load_default="client_secret_post"),
    "scopes": fields.List(fields.Str(), required=False, load_default=list),
    "extra_authorize_params": fields.Dict(data_key="extraAuthorizeParams", required=False, load_default=dict),
    "protocol_type": fields.Str(data_key="protocolType", required=False, load_default="oauth2"),
})
def save_client_config(
    client_id, client_secret, server_identifier, display_name,
    categories, authorization_endpoint, token_endpoint,
    token_endpoint_auth_method, scopes, extra_authorize_params,
    protocol_type,
):
    """Save or update OAuth client credentials for an auth server (admin only)."""
    try:
        config = ClientConfig(
            client_id=client_id,
            client_secret=client_secret,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            token_endpoint_auth_method=token_endpoint_auth_method,
            scopes=scopes,
            extra_authorize_params=extra_authorize_params,
            protocol_type=protocol_type,
            server_identifier=server_identifier,
            display_name=display_name,
            categories=categories,
        )

        store = current_app.container.server_config_store
        store.save(user_id="", config=config)
        data = config.model_dump()
        if data.get("client_secret"):
            data["client_secret"] = "***"
        return jsonify(data), 201

    except Exception as e:
        logger.exception("Failed to save client config")
        return jsonify({"error": "Failed to save client config"}), 400


@credentials_bp.route("/client-config.get", methods=["GET"])
@require_admin_access
@from_query({
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
})
def get_client_config(server_identifier):
    """Get OAuth client config for an auth server (admin only; secret is masked)."""
    try:
        store = current_app.container.server_config_store
        config = store.find_by_server(user_id="", server_identifier=server_identifier)
        if not config:
            return jsonify({"error": "Client config not found"}), 404

        data = config.model_dump()
        if data.get("client_secret"):
            data["client_secret"] = "***"

        return jsonify(data), 200

    except Exception as e:
        logger.exception("Failed to get client config")
        return jsonify({"error": "Failed to get client config"}), 400
