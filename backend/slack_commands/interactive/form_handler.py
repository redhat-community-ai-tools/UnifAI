"""Interactive form handler — Block Kit modal for running workflows."""
import json
import logging

from global_utils.identity_client import IdentityClient
from slack_commands.execution.session_executor import SessionExecutor
from slack_commands.http import MAS_TIMEOUT, mas_get

logger = logging.getLogger(__name__)

CALLBACK_ID = "form_run_workflow"
ACTION_SCOPE = "form_scope_select"
ACTION_TEAM = "form_team_select"
ACTION_WORKFLOW = "form_workflow_select"

_SCOPE_PERSONAL = "personal"
_SCOPE_TEAM = "team"


class FormHandler:
    """Handles the Slack `/unifai form` interactive modal flow (open, update, submit)."""
    
    def __init__(self, mas_url: str, identity_client: IdentityClient, executor: SessionExecutor):
        self._mas_url = mas_url.rstrip("/")
        self._identity = identity_client
        self._executor = executor

    def register(self, app):
        app.action(ACTION_SCOPE)(self._on_scope_change)
        app.action(ACTION_TEAM)(self._on_team_change)
        app.action(ACTION_WORKFLOW)(self._on_workflow_select)
        app.view(CALLBACK_ID)(self._on_submit)

    # ── Open modal ───────────────────────────────────────────────

    def open_form(self, client, trigger_id: str, user_name: str, user_id: str):
        workflows = self._fetch_workflows(user_name)
        view = self._build_view(
            scope=_SCOPE_PERSONAL,
            workflows=workflows,
            metadata={"user_name": user_name, "user_id": user_id},
        )
        client.views_open(trigger_id=trigger_id, view=view)

    # ── Action handlers ──────────────────────────────────────────

    def _on_scope_change(self, ack, body, client):
        ack()
        meta = json.loads(body["view"].get("private_metadata", "{}"))
        user_name = meta.get("user_name", "")
        selected = body["actions"][0]["selected_option"]["value"]

        if selected == _SCOPE_TEAM:
            teams = self._fetch_teams(user_name)
            view = self._build_view(
                scope=_SCOPE_TEAM,
                workflows=[],
                teams=teams,
                metadata=meta,
            )
        else:
            workflows = self._fetch_workflows(user_name)
            view = self._build_view(
                scope=_SCOPE_PERSONAL,
                workflows=workflows,
                metadata=meta,
            )

        client.views_update(view_id=body["view"]["id"], view=view)

    def _on_team_change(self, ack, body, client):
        ack()
        meta = json.loads(body["view"].get("private_metadata", "{}"))
        user_name = meta.get("user_name", "")
        team_uid = body["actions"][0]["selected_option"]["value"]

        teams = self._fetch_teams(user_name)
        workflows = self._fetch_workflows(user_name, team_uid=team_uid)

        view = self._build_view(
            scope=_SCOPE_TEAM,
            workflows=workflows,
            teams=teams,
            selected_team=team_uid,
            metadata=meta,
        )
        client.views_update(view_id=body["view"]["id"], view=view)

    def _on_workflow_select(self, ack, body, client):
        ack()

    # ── View submission ──────────────────────────────────────────

    def _on_submit(self, ack, body, client):
        ack()
        meta = json.loads(body["view"].get("private_metadata", "{}"))
        user_name = meta.get("user_name", "")
        user_id = body["user"]["id"]

        values = body["view"]["state"]["values"]

        scope = values.get("scope_block", {}).get(ACTION_SCOPE, {})
        scope_value = (scope.get("selected_option") or {}).get("value", _SCOPE_PERSONAL)

        team_uid = None
        if scope_value == _SCOPE_TEAM:
            team_sel = values.get("team_block", {}).get(ACTION_TEAM, {})
            team_uid = (team_sel.get("selected_option") or {}).get("value")

        wf_sel = values.get("workflow_block", {}).get(ACTION_WORKFLOW, {})
        selected_wf = (wf_sel.get("selected_option") or {}).get("value")

        prompt_val = values.get("prompt_block", {}).get("form_prompt_input", {})
        prompt = (prompt_val.get("value") or "").strip()

        if not selected_wf:
            self._post_error(client, user_id, "Please select a workflow.")
            return
        if not prompt:
            self._post_error(client, user_id, "Please enter a prompt.")
            return

        wf_label = selected_wf
        for opt in self._fetch_workflows(user_name, team_uid=team_uid):
            if opt.get("blueprint_id") == selected_wf:
                wf_label = opt.get("name") or selected_wf
                break

        scope_label = f" (team `{team_uid}`)" if team_uid else ""
        client.chat_postMessage(
            channel=user_id,
            text=f":hourglass: Running *{wf_label}*{scope_label} with your question...",
        )

        def reply_fn(text):
            client.chat_postMessage(channel=user_id, text=text)

        self._executor.run_new_session(
            user_name=user_name,
            workflow_id=selected_wf,
            question=prompt,
            team_uid=team_uid,
            reply_fn=reply_fn,
        )

    # ── View builder ─────────────────────────────────────────────

    def _build_view(self, scope, workflows, teams=None, selected_team=None, metadata=None):
        blocks = []

        blocks.append({
            "type": "input",
            "block_id": "scope_block",
            "dispatch_action": True,
            "label": {"type": "plain_text", "text": "Scope"},
            "element": {
                "type": "static_select",
                "action_id": ACTION_SCOPE,
                "placeholder": {"type": "plain_text", "text": "Choose scope"},
                "options": [
                    {"text": {"type": "plain_text", "text": "Personal"}, "value": _SCOPE_PERSONAL},
                    {"text": {"type": "plain_text", "text": "Team"}, "value": _SCOPE_TEAM},
                ],
                "initial_option": {
                    "text": {"type": "plain_text", "text": "Team" if scope == _SCOPE_TEAM else "Personal"},
                    "value": scope,
                },
            },
        })

        if scope == _SCOPE_TEAM:
            team_options = [
                {
                    "text": {"type": "plain_text", "text": t.get("name") or t.get("team_id", "?")},
                    "value": t.get("team_id", ""),
                }
                for t in (teams or [])
                if t.get("team_id")
            ]

            team_element = {
                "type": "static_select",
                "action_id": ACTION_TEAM,
                "placeholder": {"type": "plain_text", "text": "Choose a team"},
            }
            if team_options:
                team_element["options"] = team_options
            else:
                team_element["options"] = [
                    {"text": {"type": "plain_text", "text": "No teams found"}, "value": "_none"},
                ]

            if selected_team:
                for opt in team_options:
                    if opt["value"] == selected_team:
                        team_element["initial_option"] = opt
                        break

            blocks.append({
                "type": "input",
                "block_id": "team_block",
                "dispatch_action": True,
                "label": {"type": "plain_text", "text": "Team"},
                "element": team_element,
            })

        wf_options = [
            {
                "text": {"type": "plain_text", "text": self._wf_label(wf)},
                "value": wf.get("blueprint_id", ""),
            }
            for wf in (workflows or [])
            if wf.get("blueprint_id")
        ]

        wf_element = {
            "type": "static_select",
            "action_id": ACTION_WORKFLOW,
            "placeholder": {"type": "plain_text", "text": "Choose a workflow"},
        }
        if wf_options:
            wf_element["options"] = wf_options
        else:
            wf_element["options"] = [
                {"text": {"type": "plain_text", "text": "No workflows available"}, "value": "_none"},
            ]

        blocks.append({
            "type": "input",
            "block_id": "workflow_block",
            "dispatch_action": True,
            "label": {"type": "plain_text", "text": "Workflow"},
            "element": wf_element,
        })

        blocks.append({
            "type": "input",
            "block_id": "prompt_block",
            "label": {"type": "plain_text", "text": "Prompt"},
            "element": {
                "type": "plain_text_input",
                "action_id": "form_prompt_input",
                "multiline": True,
                "placeholder": {"type": "plain_text", "text": "Enter your question..."},
            },
        })

        return {
            "type": "modal",
            "callback_id": CALLBACK_ID,
            "title": {"type": "plain_text", "text": "Run Workflow"},
            "submit": {"type": "plain_text", "text": "Run"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "private_metadata": json.dumps(metadata or {}),
            "blocks": blocks,
        }

    # ── Data fetching ────────────────────────────────────────────

    def _fetch_workflows(self, user_name, team_uid=None):
        if team_uid:
            params = {"teamId": team_uid}
        else:
            params = {"userId": user_name, "identityType": "user"}
        try:
            resp = mas_get(
                f"{self._mas_url}/api/blueprints/available.blueprints.summary.get",
                user_name,
                params=params,
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            logger.exception("Failed to fetch workflows for form")
            return []

    def _fetch_teams(self, user_name):
        try:
            return self._identity.list_teams_for_user(user_name)
        except Exception:
            logger.exception("Failed to fetch teams for form")
            return []

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _wf_label(wf):
        name = wf.get("name") or wf.get("spec_dict", {}).get("name") or wf.get("blueprint_id", "?")
        if len(name) > 70:
            name = name[:67] + "..."
        return name

    @staticmethod
    def _post_error(client, channel_id, text):
        client.chat_postMessage(channel=channel_id, text=f":x: {text}")
