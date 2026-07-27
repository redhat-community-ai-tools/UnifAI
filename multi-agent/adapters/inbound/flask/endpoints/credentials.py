"""
Flask endpoints for the credentials lifecycle.

Routes:
  POST /api/credentials/exchange              — Exchange auth code for tokens (internal, from SSO pod)
  GET  /api/credentials/status                — Check token status for a user + server
  POST /api/credentials/client-config.save    — Save OAuth client credentials for an auth server
  GET  /api/credentials/client-config.get     — Get OAuth client config for an auth server
"""

import logging

from flask import Blueprint, jsonify, request, current_app
from global_utils.helpers.apiargs import from_body, from_query
from global_utils.utils.async_bridge import get_async_bridge
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
@from_query({
    "user_id": fields.Str(data_key="userId", required=True),
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
})
def token_status(user_id, server_identifier):
    """Check whether a user has a valid credential for an auth server."""
    try:
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
@from_body({
    "client_id": fields.Str(data_key="clientId", required=True),
    "client_secret": fields.Str(data_key="clientSecret", required=False, load_default=None),
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
    "authorization_endpoint": fields.Str(data_key="authorizationEndpoint", required=False, load_default=""),
    "token_endpoint": fields.Str(data_key="tokenEndpoint", required=False, load_default=""),
    "scopes": fields.List(fields.Str(), required=False, load_default=[]),
    "extra_authorize_params": fields.Dict(data_key="extraAuthorizeParams", required=False, load_default={}),
    "protocol_type": fields.Str(data_key="protocolType", required=False, load_default="oauth2"),
})
def save_client_config(
    client_id, client_secret, server_identifier,
    authorization_endpoint, token_endpoint, scopes,
    extra_authorize_params, protocol_type,
):
    """Save or update OAuth client credentials for an auth server."""
    try:
        config = ClientConfig(
            client_id=client_id,
            client_secret=client_secret,
            authorization_endpoint=authorization_endpoint,
            token_endpoint=token_endpoint,
            scopes=scopes,
            extra_authorize_params=extra_authorize_params,
            protocol_type=protocol_type,
            server_identifier=server_identifier,
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
@from_query({
    "server_identifier": fields.Str(data_key="serverIdentifier", required=True),
})
def get_client_config(server_identifier):
    """Get OAuth client config for an auth server (secret is masked)."""
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
