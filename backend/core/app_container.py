from pymongo import MongoClient

from admin_config.action_dispatcher import ActionDispatcher
from admin_config.repository.mongo_repository import MongoAdminConfigRepository
from admin_config.service import AdminConfigService
from admin_config.template import ADMIN_CONFIG_TEMPLATE
from config.app_config import AppConfig
from global_utils.identity_client import IdentityClient
from global_utils.redis import RedisKVStore, TeamMembershipCache, build_redis_client
from global_utils.utils.singleton import SingletonMeta
from global_utils.utils.util import get_mongo_url

from slack_commands.commands.ask import AskCommand
from slack_commands.interactive.form_handler import FormHandler
from slack_commands.commands.cancel import CancelCommand
from slack_commands.commands.delete import DeleteCommand
from slack_commands.commands.health import HealthCommand
from slack_commands.commands.help import HelpCommand
from slack_commands.commands.history import HistoryCommand
from slack_commands.commands.list_teams import ListTeamsCommand
from slack_commands.commands.list_workflows import ListWorkflowsCommand
from slack_commands.commands.list_sessions import ListSessionsCommand
from slack_commands.commands.session_status import StatusCommand
from slack_commands.commands.whoami import WhoamiCommand
from slack_commands.execution.session_executor import SessionExecutor
from slack_commands.service import SlackCommandsService


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root for the platform backend.

    All wiring lives here:
      - owns the shared MongoClient (single connection pool)
      - reads collection names from AppConfig
      - owns the ActionDispatcher for server-side side-effects
      - owns the SlackCommandsService for slash command handling
    """

    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        mongo_client = MongoClient(get_mongo_url())
        db = mongo_client[cfg.mongo_db]

        # ── Admin Config ─────────────────────────────────────────────
        self.admin_config_repo = MongoAdminConfigRepository(
            collection=db[cfg.admin_config_coll],
        )

        self.action_dispatcher = ActionDispatcher(
            service_urls={"rag": cfg.rag_url},
        )

        self.admin_config_service = AdminConfigService(
            repository=self.admin_config_repo,
            template=ADMIN_CONFIG_TEMPLATE,
            action_dispatcher=self.action_dispatcher,
        )

        # ── Identity ─────────────────────────────────────────────────
        self.redis_kv_store = RedisKVStore(build_redis_client())
        self.team_membership_cache = TeamMembershipCache(self.redis_kv_store)
        self.identity_client = IdentityClient(
            base_url=(cfg.identity_host or "").rstrip("/"),
            team_cache=self.team_membership_cache,
        )

        # ── Slack Commands ───────────────────────────────────────────
        mas_url = cfg.multiagent_url
        session_executor = SessionExecutor(base_url=mas_url)

        self.slack_commands_service = SlackCommandsService(
            handlers={
                "help": HelpCommand(),
                "health": HealthCommand(),
                "whoami": WhoamiCommand(),
                "teams": ListTeamsCommand(identity_client=self.identity_client),
                "list": ListSessionsCommand(base_url=mas_url),
                "workflows": ListWorkflowsCommand(base_url=mas_url, identity_client=self.identity_client),
                "ask": AskCommand(base_url=mas_url, executor=session_executor, identity_client=self.identity_client),
                "status": StatusCommand(base_url=mas_url),
                "cancel": CancelCommand(base_url=mas_url),
                "delete": DeleteCommand(base_url=mas_url),
                "history": HistoryCommand(base_url=mas_url),
            }
        )

        # ── Interactive (modals) ─────────────────────────────────────
        self.form_handler = FormHandler(
            mas_url=mas_url,
            identity_client=self.identity_client,
            executor=session_executor,
        )

        self._initialized = True
