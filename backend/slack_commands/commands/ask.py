"""Ask command — creates or continues a session against a workflow.

Thin handler: parses input, resolves workflow/session, and delegates
the long-running execution to SessionExecutor (deferred response pattern).
"""
import logging
import re
from typing import Optional, Union

import requests

from global_utils.identity_client import IdentityClient
from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.execution.session_executor import SessionExecutor
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse, sanitize_slack_arg

logger = logging.getLogger(__name__)

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_TEAM_FLAG = re.compile(r"--team\s+(\S+)", re.IGNORECASE)


class AskCommand(CommandHandler):

    def __init__(self, base_url: str, executor: SessionExecutor, identity_client: IdentityClient):
        self._url = base_url.rstrip("/")
        self._executor = executor
        self._identity = identity_client

    def handle(self, command: SlackCommand) -> SlackResponse:
        result = self._extract_team(command)
        if isinstance(result, SlackResponse):
            return result
        team_uid = result
        args = _TEAM_FLAG.sub("", command.args).strip()

        parts = args.split(maxsplit=1)

        if len(parts) < 2:
            return self._usage()

        ref, question = sanitize_slack_arg(parts[0]), parts[1]

        if _UUID_PATTERN.match(ref):
            if self._session_exists(ref, command.user_name):
                self._executor.continue_session(
                    user_name=command.user_name,
                    session_id=ref,
                    question=question,
                    response_url=command.response_url,
                    public=command.public,
                    team_uid=team_uid,
                )
                return SlackResponse(
                    text=f":hourglass: Continuing session `{ref[:8]}…` with your question...",
                )
            # UUID is not a confirmed session — treat it as a workflow ID below

        workflow_id, label = self._resolve_workflow(command.user_name, ref, team_uid=team_uid)
        if workflow_id is None:
            return label

        self._executor.run_new_session(
            user_name=command.user_name,
            workflow_id=workflow_id,
            question=question,
            response_url=command.response_url,
            public=command.public,
            team_uid=team_uid,
        )
        return SlackResponse(
            text=f":hourglass: Running *{label}* with your question...",
        )

    def _extract_team(self, command: SlackCommand) -> Union[Optional[str], SlackResponse]:
        match = _TEAM_FLAG.search(command.args)
        if not match:
            return None
        team_uid = match.group(1)
        if not self._identity.is_member(command.user_name, team_uid):
            return SlackResponse(
                text=f":x: Team `{team_uid}` not found or you are not a member.",
            )
        return team_uid

    def _session_exists(self, session_id: str, user_name: str):
        """Returns True / False / None (transient error)."""
        try:
            resp = mas_get(
                f"{self._url}/api/sessions/session.status.get",
                user_name,
                params={"sessionId": session_id},
                timeout=5,
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            return True
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return False
            logger.warning("session_exists check failed: %s", e)
            return None
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.warning("session_exists check failed: %s", e)
            return None

    def _resolve_workflow(self, user_name: str, ref: str, *, team_uid: Optional[str] = None):
        """Resolve a workflow reference (UUID or name) to (id, display_label).

        Returns (None, SlackResponse) on error so the caller can short-circuit.
        """
        if _UUID_PATTERN.match(ref):
            return ref, ref

        if team_uid:
            params = {"teamId": team_uid}
        else:
            params = {"userId": user_name, "identityType": "user"}

        try:
            resp = mas_get(
                f"{self._url}/api/blueprints/available.blueprints.summary.get",
                user_name,
                params=params,
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, operation="Workflow lookup"),
            ) from e
        workflows = resp.json()

        matches = [
            bp for bp in workflows
            if (bp.get("name") or bp.get("spec_dict", {}).get("name") or "").lower() == ref.lower()
        ]

        if len(matches) == 1:
            bp = matches[0]
            bp_id = bp.get("blueprint_id", "")
            name = bp.get("name") or bp.get("spec_dict", {}).get("name") or bp_id
            return bp_id, name

        if len(matches) > 1:
            ids = "\n".join(
                f"• `{bp.get('blueprint_id', '?')}` — {bp.get('name', '?')}"
                for bp in matches
            )
            return None, SlackResponse(
                text=(
                    f":warning: Multiple workflows named *{ref}*:\n{ids}\n"
                    f"Please use the full ID."
                ),
            )

        return None, SlackResponse(
            text=(
                f":x: No workflow found with name *{ref}*.\n"
                f"Run `/unifai workflows` to see available options."
            ),
        )

    @staticmethod
    def _usage() -> SlackResponse:
        return SlackResponse(
            text=(
                "*Usage:*\n"
                "• `/unifai ask <workflow> <question>` — Start a new session\n"
                "• `/unifai ask --team <team_uid> <workflow> <question>` — Start with a team workflow\n"
                "• `/unifai ask <session_id> <question>` — Continue an existing session\n"
                "• `/unifai ask --team <team_uid> <session_id> <question>` — Continue a team session\n"
                "\nRun `/unifai workflows` to see available workflows.\n"
                "Run `/unifai teams` to see your team UIDs."
            ),
        )
