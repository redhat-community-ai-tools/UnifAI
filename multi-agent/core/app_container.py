from catalog.element_registry import ElementRegistry
from catalog.service import CatalogService
from blueprints.repository.mongo_blueprint_repository import MongoBlueprintRepository
from blueprints.service import BlueprintService
from blueprints.resolver import BlueprintResolver
from session.workflow_session_factory import WorkflowSessionFactory
from session.repository.mongo_session_repository import MongoSessionRepository
from session.user_session_manager import UserSessionManager
from session.session_executor import SessionExecutor
from session.service import SessionService
from resources.registry import ResourcesRegistry
from resources.service import ResourcesService
from resources.repository.mongo_repository import MongoResourceRepository
from graph.service import GraphService
from graph.validation.service import GraphValidationService
from actions.service import ActionsService
from sharing.repository.mongo_repository import MongoShareRepository
from sharing.cloner import ShareCloner
from sharing.service import ShareService
from statistics.service import StatisticsService
from config.app_config import AppConfig
from global_utils.utils.singleton import SingletonMeta


class AppContainer(metaclass=SingletonMeta):
    """
    Central composition root.  All wiring lives here, but no magic strings:
      • reads collection names   from AppConfig
      • reads engine_name        from AppConfig
      • reads mongo_uri & db     from AppConfig
    """

    def __init__(self, cfg: AppConfig):
        # idempotent guard
        if getattr(self, "_initialized", False):
            return

        # plugin discovery
        self.element_registry = ElementRegistry()
        self.element_registry.auto_discover()

        # actions service (independent of element registry)
        self.actions_service = ActionsService()
        # auto-discover and register all actions
        self.actions_service.auto_discover_actions()

        # catalog service
        self.catalog_service = CatalogService(self.element_registry)

        # Graph service (building only)
        self.graph_service = GraphService(self.element_registry)
        
        # Graph validation service (validation only)
        self.graph_validation_service = GraphValidationService(self.element_registry)

        # blueprint catalog
        self.blueprint_repo = MongoBlueprintRepository(
            db_name=cfg.mongo_db,
            coll_name=cfg.blueprint_coll
        )

        # resource registry
        resource_registry = ResourcesRegistry(repo=MongoResourceRepository(cfg.mongodb_port,
                                                                           mongodb_ip=cfg.mongodb_ip,
                                                                           db_name=cfg.mongo_db,
                                                                           coll_name=cfg.resources_coll),
                                              bp_repo=self.blueprint_repo)

        # resources service
        self.resources_service = ResourcesService(resource_registry=resource_registry,
                                                  element_registry=self.element_registry)
        # blueprint resolver
        self.blueprint_resolver = BlueprintResolver(resource_registry=resource_registry,
                                                    element_registry=self.element_registry)

        # blueprint service
        self.blueprint_service = BlueprintService(self.blueprint_repo, resolver=self.blueprint_resolver)

        # session orchestration
        self.session_factory = WorkflowSessionFactory(
            element_registry=self.element_registry,
            engine_name=cfg.engine_name
        )
        self.session_repo = MongoSessionRepository(
            mongodb_port=cfg.mongodb_port,
            mongodb_ip=cfg.mongodb_ip,
            db_name=cfg.mongo_db,
            collection_name=cfg.session_coll
        )
        self.session_manager = UserSessionManager(
            repository=self.session_repo,
            session_factory=self.session_factory,
            blueprint_service=self.blueprint_service
        )
        self.session_executor = SessionExecutor(
            session_manager=self.session_manager,
            repository=self.session_repo
        )

        self.session_service = SessionService(
            manager=self.session_manager,
            executor=self.session_executor
        )

        # sharing service
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

        self._initialized = True
