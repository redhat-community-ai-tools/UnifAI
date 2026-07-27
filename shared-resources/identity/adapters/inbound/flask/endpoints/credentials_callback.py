"""
Credentials Callback Relay

Receives OAuth callbacks from external authorization servers (GitHub, Atlassian, etc.)
and relays the authorization code + state to the multi-agent backend for token exchange.

The SSO pod is publicly accessible, so it can receive OAuth redirects.
The multi-agent pod is behind a VPN, so it cannot receive direct callbacks.
This route bridges that gap.

After the exchange, the popup is given a small HTML page that posts the result
back to the parent window via postMessage and closes itself.
"""

import json
import logging

import requests
from flask import Blueprint, request, make_response

from config.app_config import AppConfig

logger = logging.getLogger(__name__)

credentials_bp = Blueprint("credentials", __name__)

_POPUP_CLOSE_TEMPLATE = """\
<!DOCTYPE html>
<html><head><title>Sign In</title></head>
<body>
<p id="msg">Completing sign-in&hellip;</p>
<script>
(function() {{
  var payload = {payload_json};
  var targetOrigin = {target_origin};
  if (window.opener) {{
    window.opener.postMessage(payload, targetOrigin);
  }}
  document.getElementById("msg").textContent = payload.success
    ? "Signed in! You can close this window."
    : "Error: " + (payload.error || "unknown");
  setTimeout(function() {{ window.close(); }}, 1200);
}})();
</script>
</body></html>
"""


def _popup_response(payload: dict):
    """Return a small HTML page that posts *payload* to the opener and closes."""
    config = AppConfig.get_instance()
    frontend_url = getattr(config, "frontend_url", "*") or "*"
    html = _POPUP_CLOSE_TEMPLATE.format(
        payload_json=json.dumps(payload),
        target_origin=json.dumps(frontend_url),
    )
    resp = make_response(html, 200)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


@credentials_bp.route("/callback", methods=["GET"])
def credentials_callback():
    """
    Receive OAuth callback from an external authorization server.

    Query params (from the AS redirect):
      - code: authorization code
      - state: HMAC-signed state parameter

    Forwards code + state to multi-agent's exchange endpoint,
    then returns a small self-closing HTML page that notifies the parent window.
    """
    config = AppConfig.get_instance()

    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")
    error_description = request.args.get("error_description", "")

    if error:
        logger.error("OAuth error from AS: %s — %s", error, error_description)
        return _popup_response({
            "type": "credentials_callback",
            "success": False,
            "error": error_description or error,
        })

    if not code or not state:
        return _popup_response({
            "type": "credentials_callback",
            "success": False,
            "error": "Missing code or state",
        })

    multi_agent_url = f"http://{config.multiagent_host}:{config.multiagent_port}/api/credentials/exchange"
    try:
        resp = requests.post(
            multi_agent_url,
            json={"code": code, "state": state},
            headers={
                "Content-Type": "application/json",
            },
            timeout=15,
        )

        if resp.status_code == 200:
            return _popup_response({
                "type": "credentials_callback",
                "success": True,
            })
        else:
            error_msg = resp.json().get("error", "Token exchange failed")
            logger.error("Token exchange failed: %s", error_msg)
            return _popup_response({
                "type": "credentials_callback",
                "success": False,
                "error": error_msg,
            })

    except requests.RequestException as exc:
        logger.error("Failed to reach multi-agent for token exchange: %s", exc)
        return _popup_response({
            "type": "credentials_callback",
            "success": False,
            "error": "Internal communication error",
        })
