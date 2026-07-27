"""Domain models for Slack slash commands."""
import re
from typing import Optional

from pydantic import BaseModel

_WRAP_TICKS = re.compile(r"^`(.+)`$")


def sanitize_slack_arg(value: str) -> str:
    """Strip wrapping backticks that Slack adds around pasted IDs/names."""
    v = (value or "").strip()
    m = _WRAP_TICKS.match(v)
    return m.group(1).strip() if m else v


_REQUIRED_FIELDS = ("command", "user_id", "user_name", "response_url")


_PUBLIC_FLAG = re.compile(r"\s+--public\b", re.IGNORECASE)


class SlackCommand(BaseModel):
    """Parsed incoming slash command from Slack."""
    command: str
    text: str
    subcommand: str
    args: str
    user_id: str
    user_name: str
    channel_id: str
    channel_name: str
    team_id: str
    response_url: str
    public: bool = False

    @classmethod
    def validate_payload(cls, form: dict) -> Optional[str]:
        """Return the name of the first missing required field, or None."""
        for field in _REQUIRED_FIELDS:
            if not form.get(field):
                return field
        return None

    @classmethod
    def from_form(cls, form: dict) -> "SlackCommand":
        raw_text = (form.get("text") or "").strip()
        public = bool(_PUBLIC_FLAG.search(raw_text))
        text = _PUBLIC_FLAG.sub("", raw_text).strip()

        parts = text.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1].strip() if len(parts) > 1 else ""

        return cls(
            command=form.get("command", ""),
            text=text,
            subcommand=subcommand,
            args=args,
            user_id=form.get("user_id", ""),
            user_name=form.get("user_name", ""),
            channel_id=form.get("channel_id", ""),
            channel_name=form.get("channel_name", ""),
            team_id=form.get("team_id", ""),
            response_url=form.get("response_url", ""),
            public=public,
        )


class MASRequestError(Exception):
    """Raised by command handlers when a MAS HTTP request fails."""

    def __init__(self, slack_response: "SlackResponse"):
        self.slack_response = slack_response
        super().__init__(slack_response.text)


class SlackResponse(BaseModel):
    """Response to send back to Slack."""
    text: str
    response_type: str = "ephemeral"
    blocks: Optional[list] = None

    def with_visibility(self, command: "SlackCommand") -> "SlackResponse":
        """Override response_type to in_channel when the user passes --public."""
        if command.public:
            return self.model_copy(update={"response_type": "in_channel"})
        return self

    def to_dict(self) -> dict:
        result = {
            "response_type": self.response_type,
            "text": self.text,
        }
        if self.blocks:
            result["blocks"] = self.blocks
        return result
