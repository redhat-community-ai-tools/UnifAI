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


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root for the platform backend.

    All wiring lives here:
      - owns the shared MongoClient (single connection pool)
      - reads collection names from AppConfig
      - owns the ActionDispatcher for server-side side-effects
    """

    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        mongo_client = MongoClient(get_mongo_url())
        db = mongo_client[cfg.mongo_db]

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

        self.redis_kv_store = RedisKVStore(build_redis_client())
        self.team_membership_cache = TeamMembershipCache(self.redis_kv_store)
        self.identity_client = IdentityClient(
            base_url=(cfg.identity_host or "").rstrip("/"),
            team_cache=self.team_membership_cache,
        )

        self._initialized = True
