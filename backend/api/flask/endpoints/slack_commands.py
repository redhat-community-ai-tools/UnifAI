"""Slack slash commands — inbound HTTP adapter.

Thin layer: verifies the request signature, parses the Slack form payload,
delegates to the service, and returns the response.
"""
import logging

from flask import Blueprint, current_app, jsonify, request

from config.app_config import AppConfig
from global_utils.flask.decorators import require_slack_signature
from slack_commands.models import SlackCommand, SlackResponse

logger = logging.getLogger(__name__)

slack_commands_bp = Blueprint("slack_commands", __name__)

_verify_slack = require_slack_signature(
    get_signing_secret=lambda: AppConfig.get_instance().get("slack_signing_secret", ""),
)

@slack_commands_bp.route("/commands", methods=["POST"])
@_verify_slack
def handle_slash_command():
    """
    Receive a Slack slash command POST (application/x-www-form-urlencoded).

    Parses into a SlackCommand, delegates to SlackCommandsService,
    and returns the formatted Slack JSON response.
    """
    missing = SlackCommand.validate_payload(request.form)
    if missing:
        return jsonify({"error": f"Missing required field: {missing}"}), 400

    command = SlackCommand.from_form(request.form)
    service = current_app.container.slack_commands_service
    try:
        response = service.execute(command)
    except Exception:
        logger.exception("Unexpected error handling slash command")
        response = SlackResponse(text=":x: Command failed. Please try again later.")
    return jsonify(response.to_dict()), 200
