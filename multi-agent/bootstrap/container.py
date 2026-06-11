"""
Composition root — the outermost ring of the architecture.

This is the single place that knows about BOTH the domain hexagon (mas.*)
AND the concrete adapter implementations (outbound.*).  It wires ports
to adapters and assembles the full object graph.

No domain or adapter code should ever import this module.  Only entry
points (run/dev.py, run/wsgi.py, inbound/temporal/__main__.py, …)
create an AppContainer and pass it — or individual services from it —
into the layers that need them.
"""
import logging

from mas.catalog.element_registry import ElementRegistry
from mas.catalog.service import CatalogService
from mas.catalog.card_service import ElementCardService
from mas.blueprints.service import BlueprintService
from mas.blueprints.resolver import BlueprintResolver
from mas.session.building import WorkflowSessionFactory
from mas.session.management import UserSessionManager
from mas.session.execution import SessionLifecycle, ForegroundSessionRunner, SessionInputProjector
from mas.session.service import SessionService
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import ResourcesService
from mas.graph.service import GraphService
from mas.graph.validation.service import GraphValidationService
from mas.actions.service import ActionsService
from mas.sharing.cloner import ShareCloner
from mas.sharing.service import ShareService
from mas.statistics.service import StatisticsService
from mas.validation.service import ElementValidationService
from mas.templates.service import TemplateService
from mas.collaboration.service import CollaborationService

# Auth layer
from mas.core.auth.service import AuthService, AuthStrategyRegistry
from mas.core.auth.discovery import AuthDetector
from outbound.auth.oauth2_strategy import OAuth2Strategy
from mas.core.auth.strategies.oauth2.detection import OAuth2DetectionStrategy
from mas.core.auth.strategies.oauth2.state_manager import OAuthStateManager
from outbound.auth.api_key_strategy import ApiKeyStrategy
from outbound.mongo.client_config_repository import MongoServerConfigStore
from mas.actions.auth.authenticate.action import AuthenticateAction
from mas.actions.providers.mcp.validate_connection.validate_connection import ValidateConnectionAction
from mas.actions.providers.mcp.get_tools_names.get_tools_names import GetToolsNamesAction

from config.app_config import AppConfig
from mas.core.platform_config import PlatformConfig
from outbound.storage import LocalSessionStorageCleaner

from outbound.mongo import (
    MongoBlueprintRepository,
    MongoSessionRepository,
    MongoResourceRepository,
    MongoShareRepository,
    MongoTemplateRepository,
)
# Auth layer — adapters
from outbound.mongo.auth_token_repository import MongoCredentialStore
from outbound.redis.auth_pending_store import RedisFlowStateStore
from outbound.auth.http_oauth_client import HttpxAuthClient

from mas.core.identity.ports import IdentityProvider
from global_utils.identity_client import IdentityClient
from global_utils.utils.singleton import SingletonMeta
from global_utils.utils.util import get_redis_url


logger = logging.getLogger(__name__)


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root.  All wiring lives here:
      - reads collection names   from AppConfig
      - reads engine_name        from AppConfig
      - reads mongo_uri & db     from AppConfig
    """

    def __init__(self, cfg: AppConfig):
        if getattr(self, "_initialized", False):
            return

        self.element_registry = ElementRegistry()
        self.element_registry.auto_discover()

        self.actions_service = ActionsService()
        self.actions_service.auto_discover_actions()

        self.catalog_service = CatalogService(self.element_registry)

        self.graph_service = GraphService(self.element_registry)
        self.graph_validation_service = GraphValidationService(self.element_registry)

        self.validation_service = ElementValidationService(
            element_registry=self.element_registry
        )

        self.card_service = ElementCardService(
            element_registry=self.element_registry
        )

        self.blueprint_repo = MongoBlueprintRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.blueprint_coll
        )

        self.resource_repo = MongoResourceRepository(
            cfg.mongodb_port,
            mongodb_ip=cfg.mongodb_ip,
            db_name=cfg.mongo_db,
            coll_name=cfg.resources_coll,
        )

        resource_registry = ResourcesRegistry(
            repo=self.resource_repo,
            bp_repo=self.blueprint_repo,
        )

        self.resources_service = ResourcesService(
            resource_registry=resource_registry,
            element_registry=self.element_registry,
            validation_service=self.validation_service,
            card_service=self.card_service,
        )

        self.blueprint_resolver = BlueprintResolver(
            resource_registry=resource_registry,
            element_registry=self.element_registry
        )

        self.blueprint_service = BlueprintService(
            self.blueprint_repo,
            resolver=self.blueprint_resolver,
            validation_service=self.validation_service,
            card_service=self.card_service,
        )

        # ── Auth layer ────────────────────────────────────────────────

        http_client = HttpxAuthClient()
        self.credential_store = MongoCredentialStore(
            mongodb_ip=cfg.mongodb_ip,
            mongodb_port=cfg.mongodb_port,
            db_name=cfg.mongo_db,
            coll_name=cfg.credentials_coll,
            encryption_key=cfg.credential_encryption_key,
        )

        redis_url = get_redis_url()
        pending_store = None
        if redis_url:
            import redis as redis_lib
            redis_client = redis_lib.Redis.from_url(redis_url, socket_timeout=30)
            pending_store = RedisFlowStateStore(
                redis_client=redis_client,
                encryption_key=cfg.credential_encryption_key,
            )

        # Detection
        oauth2_detection = OAuth2DetectionStrategy()
        detector = AuthDetector(
            strategies=[oauth2_detection],
            http_client=http_client,
        )

        # Server config store
        self.server_config_store = MongoServerConfigStore(
            mongodb_ip=cfg.mongodb_ip,
            mongodb_port=cfg.mongodb_port,
            db_name=cfg.mongo_db,
            coll_name="server_configs",
        )

        # OAuth2 state manager
        if not cfg.mcp_auth_state_secret:
            logger.warning("MCP_AUTH_STATE_SECRET not set — using random key (sessions won't survive restarts)")
            import secrets as _secrets
            cfg.mcp_auth_state_secret = _secrets.token_urlsafe(32)
        state_manager = OAuthStateManager(secret=cfg.mcp_auth_state_secret)

        # Strategy registry — self-contained strategies
        oauth2_strategy = OAuth2Strategy(
            pending_store=pending_store,
            state_manager=state_manager,
            callback_url=f"{cfg.identity_host.rstrip('/')}/api/credentials/callback",
            client_config_store=self.server_config_store,
            http_client=http_client,
        )
        api_key_strategy = ApiKeyStrategy()

        strategy_registry = AuthStrategyRegistry()
        strategy_registry.register(oauth2_strategy)
        strategy_registry.register(api_key_strategy)

        # AuthService — single owner of the credential lifecycle
        self.auth_service = AuthService(
            credential_store=self.credential_store,
            strategy_registry=strategy_registry,
            server_config_store=self.server_config_store,
            detector=detector,
        )

        self.resources_service.set_auth_service(self.auth_service)
        self.blueprint_service.set_auth_service(self.auth_service)

        self.actions_service.register_instance(AuthenticateAction(
            auth_service=self.auth_service,
        ))
        self.actions_service.register_instance(ValidateConnectionAction(
            auth_service=self.auth_service,
        ))
        self.actions_service.register_instance(GetToolsNamesAction(
            auth_service=self.auth_service,
        ))

        # ── Platform config (domain-layer projection of AppConfig) ────
        self.platform_config = PlatformConfig(
            shared_storage=cfg.shared_storage,
        )

        # ── Session factory ───────────────────────────────────────────
        self.session_factory = WorkflowSessionFactory(
            element_registry=self.element_registry,
            engine_name=cfg.engine_name,
            auth_service=self.auth_service,
            platform_config=self.platform_config,
        )
        self.session_repo = MongoSessionRepository(
            mongodb_port=cfg.mongodb_port,
            mongodb_ip=cfg.mongodb_ip,
            db_name=cfg.mongo_db,
            collection_name=cfg.session_coll
        )
        self.session_storage_cleaner = LocalSessionStorageCleaner(
            base_path=cfg.shared_storage,
        )
        self.session_manager = UserSessionManager(
            repository=self.session_repo,
            session_factory=self.session_factory,
            blueprint_service=self.blueprint_service,
            platform_config=self.platform_config,
            storage_cleaner=self.session_storage_cleaner,
        )

        self.session_lifecycle = SessionLifecycle(repository=self.session_repo)
        self.input_projector = SessionInputProjector(repository=self.session_repo)

        self.channel_factory = self._create_channel_factory(cfg)

        foreground_runner = ForegroundSessionRunner(
            lifecycle=self.session_lifecycle,
            channel_factory=self.channel_factory,
        )

        background_engine = self._create_background_engine(cfg.engine_name)

        self.session_service = SessionService(
            manager=self.session_manager,
            foreground_runner=foreground_runner,
            input_projector=self.input_projector,
            background_engine=background_engine,
        )

        # Single shared IdentityClient — the only object that makes HTTP calls
        # to the Identity pod.  The identity_provider port adapter and the
        # directory provider both delegate to it.
        identity_base = (cfg.directory_sso_url or cfg.identity_host or "").rstrip("/")
        self.identity_client = IdentityClient(base_url=identity_base)

        self.identity_provider: IdentityProvider = self._build_identity_auth_provider(
            cfg, self.identity_client
        )

        self.directory_provider = self._build_directory_provider(cfg, self.identity_client)

        self.share_repo = MongoShareRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.shares_coll
        )
        self.share_cloner = ShareCloner(
            resources_registry=resource_registry,
            blueprint_service=self.blueprint_service,
            element_registry=self.element_registry
        )
        self.share_service = ShareService(
            share_repository=self.share_repo,
            cloner=self.share_cloner
        )

        self.statistics_service = StatisticsService(
            blueprint_service=self.blueprint_service,
            session_service=self.session_service,
            resources_service=self.resources_service
        )

        self.template_repo = MongoTemplateRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.templates_coll
        )
        self.template_service = TemplateService(
            repository=self.template_repo,
            element_registry=self.element_registry,
            blueprint_service=self.blueprint_service,
            resources_service=self.resources_service,
        )

        self.collaboration_service = self._create_collaboration_service(
            cfg, self.session_repo, self.identity_provider
        )

        self._initialized = True

    @staticmethod
    def _create_channel_factory(cfg: AppConfig):
        redis_url = get_redis_url()
        if redis_url:
            from outbound.channels import RedisChannelFactory
            return RedisChannelFactory(
                redis_url=redis_url,
                stream_ttl=cfg.redis_stream_ttl,
                block_ms=cfg.redis_stream_block_ms,
                batch_size=cfg.redis_stream_batch_size,
            )
        from outbound.channels import LocalChannelFactory
        return LocalChannelFactory()

    @staticmethod
    def _create_collaboration_service(cfg: AppConfig, session_repo, identity_provider):
        redis_url = get_redis_url()
        if redis_url:
            from outbound.redis import RedisCollaborationStore
            store = RedisCollaborationStore(redis_url=redis_url)
            return CollaborationService(
                store=store,
                session_repo=session_repo,
                identity_provider=identity_provider,
                presence_ttl=cfg.collaboration_presence_ttl,
                edit_lock_ttl=cfg.collaboration_edit_lock_ttl_sec,
            )
        return None

    @staticmethod
    def _create_background_engine(engine_name: str):
        if engine_name == "temporal":
            from outbound.temporal.session_engine import TemporalSessionEngine
            return TemporalSessionEngine()
        return None

    @staticmethod
    def _build_identity_auth_provider(
        cfg: AppConfig, identity_client: IdentityClient
    ) -> "IdentityProvider":
        """Build the IdentityProvider adapter based on configuration.

        - "pod"  → production HTTP adapter (requires Identity pod)
        - "dev"  → permissive local-dev adapter (no external calls)
        - "noop" → single-user mode (no teams)
        - ""     → auto-detect: "pod" when identity_client is configured, else "dev"
        """
        mode = (cfg.identity_provider_mode or "").strip().lower()

        if not mode:
            mode = "pod" if identity_client.configured else "dev"

        if mode == "pod":
            from outbound.identity.identity_pod_provider import IdentityPodProvider
            logger.info("Identity provider: pod (%s)", identity_client._base)
            return IdentityPodProvider(identity_client=identity_client)

        if mode == "dev":
            from outbound.identity.dev_provider import DevIdentityProvider
            logger.info("Identity provider: dev (permissive)")
            return DevIdentityProvider()

        if mode == "noop":
            from outbound.identity.noop_provider import NoOpIdentityProvider
            logger.info("Identity provider: noop (no teams)")
            return NoOpIdentityProvider()

        raise ValueError(
            f"Unknown identity_provider_mode: '{mode}'. Supported: pod, dev, noop"
        )

    @staticmethod
    def _build_directory_provider(cfg: AppConfig, identity_client: IdentityClient):
        provider_name = cfg.directory_provider.strip().lower()
        if not provider_name:
            return None

        if provider_name == "sso":
            return AppContainer._build_directory_client(cfg, identity_client)

        raise ValueError(
            f"Unknown directory_provider: '{provider_name}'. Supported: sso"
        )

    @staticmethod
    def _build_directory_client(cfg: AppConfig, identity_client: IdentityClient):
        from outbound.identity_directory_client import IdentityDirectoryClient

        if not identity_client.configured:
            raise ValueError(
                "identity_host or directory_sso_url is required when directory_provider='sso'"
            )
        logger.info("Directory provider: identity (%s)", identity_client._base)
        return IdentityDirectoryClient(
            identity_client=identity_client,
            timeout=cfg.directory_timeout,
        )
