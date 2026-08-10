"""Slack Socket Mode adapter — connects to Slack over WebSocket.

Replaces the HTTP-based Flask endpoint for receiving slash commands.
The outbound WebSocket avoids the need for a public LoadBalancer or
Nginx proxy; Slack sends payloads over the pre-authenticated socket.

Reuses the same SlackCommandsService and command handlers as the
Flask adapter — only the transport layer changes.
"""
import os
import sys

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config.app_config import AppConfig
from core.app_container import AppContainer
from shared.logger import logger
from slack_commands.models import SlackCommand, SlackResponse


def _build_container():
    cfg = AppConfig.get_instance()
    return AppContainer(cfg)


def main():
    cfg = AppConfig.get_instance()

    bot_token = cfg.slack_bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = cfg.slack_app_token or os.environ.get("SLACK_APP_TOKEN", "")

    if not bot_token:
        logger.error("SLACK_BOT_TOKEN is not set — cannot start Socket Mode")
        sys.exit(1)
    if not app_token:
        logger.error("SLACK_APP_TOKEN is not set — cannot start Socket Mode")
        sys.exit(1)

    app = App(token=bot_token)
    container = _build_container()
    service = container.slack_commands_service
    form_handler = container.form_handler
    form_handler.register(app)

    @app.command("/unifai")
    def handle_unifai(ack, body, respond, client):
        ack()

        raw_text = (body.get("text") or "").strip().split()[0].lower() if body.get("text") else ""
        if raw_text == "form":
            form_handler.open_form(
                client=client,
                trigger_id=body["trigger_id"],
                user_name=body.get("user_name", ""),
                user_id=body.get("user_id", ""),
                channel_id=body.get("channel_id", ""),
            )
            return

        missing = SlackCommand.validate_payload(body)
        if missing:
            respond({"text": f"Missing required field: {missing}"})
            return

        command = SlackCommand.from_form(body)
        try:
            response = service.execute(command)
        except Exception:
            logger.exception("Unexpected error handling slash command")
            response = SlackResponse(text=":x: Command failed. Please try again later.")
        respond(response.to_dict())

    logger.info("Starting Slack Socket Mode handler...")
    handler = SocketModeHandler(app, app_token)
    handler.start()


if __name__ == "__main__":
    main()
