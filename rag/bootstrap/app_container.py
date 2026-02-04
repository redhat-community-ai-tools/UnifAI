"""
RAG Application Container - Composition root with singleton instances via lru_cache.

Each function creates a singleton instance on first call, then returns the cached
instance on subsequent calls. Dependencies are wired here, not scattered across
the codebase.

Usage:
    from bootstrap.app_container import pipeline_service, monitoring_service
    
    # Services are singleton - same instance returned on every call
    svc = pipeline_service()
    svc.register(pipeline_id, source_type)
"""

from functools import lru_cache
from pymongo import MongoClient

from global_utils.utils.util import get_mongo_url


# ══════════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE - Shared resources
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def mongo_client() -> MongoClient:
    """Shared MongoDB client (connection pool)."""
    return MongoClient(get_mongo_url())


@lru_cache(maxsize=1)
def pipeline_monitoring_db():
    """Database for pipeline monitoring."""
    return mongo_client()["pipeline_monitoring"]


@lru_cache(maxsize=1)
def data_sources_db():
    """Database for data sources."""
    return mongo_client()["data_sources"]


@lru_cache(maxsize=1)
def users_db():
    """Database for user data (terms approvals, etc.)."""
    return mongo_client()["users"]


@lru_cache(maxsize=1)
def file_storage():
    """Local file storage for document uploads."""
    from infrastructure.storage.local_file_storage import LocalFileStorage
    from config.app_config import AppConfig
    return LocalFileStorage(AppConfig.get_instance().upload_folder)


@lru_cache(maxsize=1)
def umami_client():
    """Umami analytics client for website tracking."""
    from infrastructure.umami.umami_client import UmamiClient
    from config.app_config import AppConfig
    config = AppConfig.get_instance()
    return UmamiClient(
        url=config.get("umami_url", ""),
        username=config.get("umami_username", ""),
        password=config.get("umami_password", ""),
    )


# ══════════════════════════════════════════════════════════════════════════════
# REPOSITORIES (Infrastructure adapters implementing domain ports)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def pipeline_repository():
    """Pipeline repository (Mongo adapter)."""
    from infrastructure.mongo.pipeline_repository import MongoPipelineRepository
    return MongoPipelineRepository(pipeline_monitoring_db()["pipelines"])


@lru_cache(maxsize=1)
def data_source_repository():
    """Data source repository (Mongo adapter)."""
    from infrastructure.mongo.data_source_repository import MongoDataSourceRepository
    return MongoDataSourceRepository(data_sources_db()["sources"])


@lru_cache(maxsize=1)
def monitoring_repository():
    """Monitoring repository (Mongo adapter)."""
    from infrastructure.mongo.monitoring_repository import MongoMonitoringRepository
    return MongoMonitoringRepository(pipeline_monitoring_db())


@lru_cache(maxsize=None)
def vector_repository(collection_name: str):
    from bootstrap.factories import VectorRepositoryFactory    
    repo = VectorRepositoryFactory.create({
        "type": "qdrant",
        "collection_name": collection_name,
        "embedding_dim": embedding_generator().embedding_dim,
    })
    repo.initialize()
    return repo


@lru_cache(maxsize=1)
def slack_channel_repository():
    """Slack channel repository (Mongo adapter)."""
    from infrastructure.mongo.data_sources.slack_channel_repository import MongoSlackChannelRepository
    return MongoSlackChannelRepository(data_sources_db()["slack_channels"])


@lru_cache(maxsize=1)
def terms_approval_repository():
    """Terms approval repository (Mongo adapter)."""
    from infrastructure.mongo.terms_approval_repository import MongoTermsApprovalRepository
    return MongoTermsApprovalRepository(users_db()["terms_user_approval"])


# ══════════════════════════════════════════════════════════════════════════════
# PROCESSORS (Domain layer - stateless data transformers)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def slack_processor():
    """Slack message processor."""
    from core.data_sources.types.slack.domain.processor import SlackProcessor
    return SlackProcessor()


@lru_cache(maxsize=1)
def document_processor():
    """Document (PDF/Markdown) processor."""
    from core.data_sources.types.document.domain.processor import DocumentProcessor
    return DocumentProcessor()


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG MANAGERS (Infrastructure layer - configuration adapters)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def slack_config_manager():
    """Slack configuration manager with tokens from AppConfig."""
    from infrastructure.sources.slack.config import SlackConfigManager
    from config.app_config import AppConfig
    
    config = AppConfig.get_instance()
    manager = SlackConfigManager()
    
    # Configure default project tokens from app config
    bot_token = config.get("default_slack_bot_token", "")
    user_token = config.get("default_slack_user_token", "")
    
    if bot_token:
        manager.set_project_tokens(
            project_id="example-project",
            bot_token=bot_token,
            user_token=user_token,
        )
        manager.set_default_project("example-project")
    
    return manager


# ══════════════════════════════════════════════════════════════════════════════
# CELERY ADAPTERS (Infrastructure layer - async task dispatch)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def celery_pipeline_dispatcher():
    """Celery adapter for pipeline task dispatch."""
    from infrastructure.celery.pipeline_dispatcher import CeleryPipelineDispatcher
    return CeleryPipelineDispatcher()


@lru_cache(maxsize=1)
def celery_slack_event_dispatcher():
    """Celery adapter for Slack event dispatch."""
    from infrastructure.celery.slack_event_dispatcher import CelerySlackEventDispatcher
    return CelerySlackEventDispatcher()


# ══════════════════════════════════════════════════════════════════════════════
# CONNECTORS (Infrastructure layer - data source adapters)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=None)
def slack_connector(project_id: str):
    """Slack connector for a specific project."""
    from infrastructure.sources.slack.connector import SlackConnector
    return SlackConnector(
        config_manager=slack_config_manager(),
        channel_repo=slack_channel_repository(),
        project_id=project_id,
    )


@lru_cache(maxsize=1)
def document_connector():
    """Document connector for PDF and other document formats."""
    from infrastructure.sources.document.connector import DocumentConnector
    return DocumentConnector()


# ══════════════════════════════════════════════════════════════════════════════
# CHUNKERS (Infrastructure layer - content splitting strategies)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def slack_chunker():
    """Slack conversation chunker with default settings."""
    from infrastructure.sources.slack.chunker import SlackChunkerStrategy
    return SlackChunkerStrategy(
        max_tokens_per_chunk=500,
        overlap_tokens=50,
        time_window_seconds=300,
    )


@lru_cache(maxsize=1)
def pdf_chunker():
    """PDF/Document chunker with default settings."""
    from infrastructure.sources.document.chunker import PDFChunkerStrategy
    return PDFChunkerStrategy(
        max_tokens_per_chunk=500,
        overlap_tokens=50,
    )


# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION SERVICES
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def pipeline_service():
    """Pipeline application service."""
    from core.pipeline.service import PipelineService
    return PipelineService(pipeline_repo=pipeline_repository())


@lru_cache(maxsize=1)
def monitoring_service():
    """Monitoring application service."""
    from core.monitoring.service import MonitoringService
    return MonitoringService(
        monitoring_repo=monitoring_repository(),
        pipeline_repo=pipeline_repository(),
    )


@lru_cache(maxsize=1)
def data_source_service():
    """Data source application service."""
    from core.data_sources.service import DataSourceService
    return DataSourceService(
        source_repo=data_source_repository(),
        pipeline_repo=pipeline_repository(),
        vector_repo_factory=vector_repository,
    )


@lru_cache(maxsize=1)
def document_service():
    """Document-specific application service."""
    from core.data_sources.types.document.document_service import DocumentService
    return DocumentService(
        data_source_service=data_source_service(),
        source_repo=data_source_repository(),
    )


@lru_cache(maxsize=1)
def doc_validators():
    """Document validators pipeline factory."""
    from core.data_sources.types.document.validators.factory import DocValidators
    from core.data_sources.types.document.validators.duplicate_validator import DuplicateValidator
    from core.data_sources.types.document.validators.extension_validator import ExtensionValidator
    from core.data_sources.types.document.validators.size_validator import SizeValidator
    from core.data_sources.types.document.validators.name_duplicate_validator import NameDuplicateValidator
    from infrastructure.sources.document.config import DocConfigManager
    from infrastructure.sources.document.validator.duplicate_checker import DocumentDuplicateCheckerAdapter
    from infrastructure.sources.document.validator.name_duplicate_checker import NameDuplicateCheckerAdapter
    
    config = DocConfigManager()
    
    # Create individual validators with their dependencies
    duplicate_validator = DuplicateValidator(
        duplicate_checker=DocumentDuplicateCheckerAdapter(data_source_repository())
    )
    extension_validator = ExtensionValidator(
        supported_extensions=config.get_supported_file_types()
    )
    size_validator = SizeValidator(
        max_file_size_bytes=config.get_config_value("max_file_size_mb", 50) * 1024 * 1024
    )
    name_duplicate_validator = NameDuplicateValidator(
        name_duplicate_checker=NameDuplicateCheckerAdapter(data_source_repository())
    )
    
    return DocValidators(
        duplicate_validator=duplicate_validator,
        extension_validator=extension_validator,
        size_validator=size_validator,
        name_duplicate_validator=name_duplicate_validator,
    )


@lru_cache(maxsize=1)
def slack_validators():
    """Slack validators pipeline factory."""
    from core.data_sources.types.slack.validators.factory import SlackValidators
    from core.data_sources.types.slack.validators.channel_bot_installation_validator import ChannelBotInstallationValidator
    from infrastructure.sources.slack.validator.bot_installation_checker import BotInstallationCheckerAdapter, MembershipUpdaterAdapter
    
    # TODO: Inject proper Slack connector based on project (None for now - graceful fallback)
    bot_checker = BotInstallationCheckerAdapter(slack_connector=None)
    membership_updater = MembershipUpdaterAdapter(storage=slack_channel_repository())
    
    return SlackValidators(
        channel_bot_validator=ChannelBotInstallationValidator(
            bot_checker=bot_checker,
            membership_updater=membership_updater,
        )
    )


def file_validation_service(username: str):
    """
    File validation service for pre-upload validation.
    
    Note: Not cached because it's user-specific (different username each time).
    """
    from core.data_sources.types.document.file_validation_service import FileValidationService
    from infrastructure.sources.document.config import DocConfigManager
    from infrastructure.sources.document.validator.name_duplicate_checker import NameDuplicateCheckerAdapter
    
    return FileValidationService(
        username=username,
        config_manager=DocConfigManager(),
        name_checker=NameDuplicateCheckerAdapter(data_source_repository()),
    )


@lru_cache(maxsize=1)
def registration_factory():
    """Registration factory for creating source-specific registrations."""
    from core.registration.factory import RegistrationFactory
    from config.app_config import AppConfig
    return RegistrationFactory(
        data_source_repository=data_source_repository(),
        upload_folder=AppConfig.get_instance().upload_folder,
        doc_validators=doc_validators(),
        slack_validators=slack_validators(),
    )


@lru_cache(maxsize=1)
def registration_service():
    """Registration service for source registration flows."""
    from core.registration.service import RegistrationService
    return RegistrationService(factory=registration_factory())


@lru_cache(maxsize=1)
def pipeline_dispatch_service():
    """Pipeline dispatch service - orchestrates registration and task dispatch."""
    from core.pipeline.dispatch_service import PipelineDispatchService
    return PipelineDispatchService(
        registration_svc=registration_service(),
        task_dispatcher=celery_pipeline_dispatcher(),
    )


@lru_cache(maxsize=1)
def slack_event_dispatch_service():
    """Slack event dispatch service - handles Slack Events API webhooks."""
    from core.data_sources.types.slack.event.dispatch_service import SlackEventDispatchService
    return SlackEventDispatchService(
        dispatcher=celery_slack_event_dispatcher(),
    )


@lru_cache(maxsize=1)
def terms_approval_service():
    """Terms approval application service."""
    from core.user.terms_approval.service import TermsApprovalService
    return TermsApprovalService(approval_repo=terms_approval_repository())


# ══════════════════════════════════════════════════════════════════════════════
# SLACK EVENTS (Application layer - event handling)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def channel_created_handler():
    """Handler for Slack channel_created events."""
    from core.data_sources.types.slack.event.handlers.channel_created import ChannelCreatedEventHandler
    return ChannelCreatedEventHandler(
        channel_repo=slack_channel_repository(),
        project_id="example-project",  # TODO: Get from config
    )


@lru_cache(maxsize=1)
def slack_event_service():
    """Slack event dispatch service with registered handlers."""
    from core.data_sources.types.slack.event.service import SlackEventService
    service = SlackEventService()
    service.register_factory("channel_created", channel_created_handler)
    return service


# ══════════════════════════════════════════════════════════════════════════════
# EMBEDDING & VECTOR COMPONENTS
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def embedding_generator():
    """Shared embedding generator (sentence transformer)."""
    from bootstrap.factories import EmbeddingGeneratorFactory
    return EmbeddingGeneratorFactory.create({"type": "sentence_transformer"})


# ══════════════════════════════════════════════════════════════════════════════
# RETRIEVAL SERVICE (Application layer - vector search orchestration)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def source_filter_resolver():
    """Filter resolver for search scoping (doc_ids, tags -> source_ids)."""
    from infrastructure.retrieval.source_filter_resolver import SourceFilterResolver
    return SourceFilterResolver(data_sources_db()["sources"])


@lru_cache(maxsize=None)
def retrieval_service(source_type: str):
    """
    Retrieval service for a specific source type.
    
    Args:
        source_type: Source type (e.g., "DOCUMENT", "SLACK")
        
    Returns:
        RetrievalService configured for the specified source type
    """
    from core.retrieval.service import RetrievalService
    return RetrievalService(
        embedder=embedding_generator(),
        vector_repo=vector_repository(f"{source_type.lower()}_data"),
        filter_resolver=source_filter_resolver(),
        source_type=source_type.upper(),
    )


# ══════════════════════════════════════════════════════════════════════════════
# STATS SERVICES (Application layer - query/aggregation use cases)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def vector_stats_service():
    """Vector storage statistics service."""
    from core.vector.stats_service import VectorStatsService
    return VectorStatsService(vector_repo_factory=vector_repository)


@lru_cache(maxsize=1)
def slack_stats_service():
    """Slack statistics aggregation service."""
    from core.data_sources.types.slack.stats_service import SlackStatsService
    return SlackStatsService(data_source_service=data_source_service())


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE HANDLERS (Application layer - source-specific orchestration)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def slack_pipeline_handler():
    """Slack pipeline handler with injected dependencies."""
    from core.data_sources.types.slack.pipeline_handler import SlackPipelineHandler
    return SlackPipelineHandler(
        connector=slack_connector("default"),
        processor=slack_processor(),
        chunker=slack_chunker(),
        embedder=embedding_generator(),
    )


@lru_cache(maxsize=1)
def document_pipeline_handler():
    """Document pipeline handler with injected dependencies."""
    from core.data_sources.types.document.pipeline_handler import DocumentPipelineHandler
    return DocumentPipelineHandler(
        connector=document_connector(),
        processor=document_processor(),
        chunker=pdf_chunker(),
        embedder=embedding_generator(),
    )


def get_pipeline_handler(source_type: str):
    """
    Resolve the appropriate pipeline handler for a source type.
    
    Args:
        source_type: Source type string (e.g., 'SLACK', 'DOCUMENT')
        
    Returns:
        SourcePipelinePort implementation for the given source type
        
    Raises:
        ValueError: If source type is not supported
    """
    handlers = {
        "SLACK": slack_pipeline_handler,
        "DOCUMENT": document_pipeline_handler,
    }
    
    factory = handlers.get(source_type.upper())
    if not factory:
        raise ValueError(f"Unsupported source type: {source_type}")
    
    return factory()


@lru_cache(maxsize=1)
def pipeline_executor():
    """Pipeline executor use case with all dependencies."""
    from core.pipeline.executor import PipelineExecutor
    return PipelineExecutor(
        pipeline_service=pipeline_service(),
        monitoring_service=monitoring_service(),
        data_source_service=data_source_service(),
        vector_repository=vector_repository,
    )


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY - Cache management for testing
# ══════════════════════════════════════════════════════════════════════════════

def clear_all_caches():
    """
    Clear all singleton caches. Useful for testing.
    
    Usage:
        from bootstrap.app_container import clear_all_caches
        clear_all_caches()  # Fresh instances will be created on next access
    """
    # Infrastructure
    mongo_client.cache_clear()
    pipeline_monitoring_db.cache_clear()
    data_sources_db.cache_clear()
    users_db.cache_clear()
    file_storage.cache_clear()
    umami_client.cache_clear()
    # Repositories
    pipeline_repository.cache_clear()
    data_source_repository.cache_clear()
    monitoring_repository.cache_clear()
    vector_repository.cache_clear()
    slack_channel_repository.cache_clear()
    terms_approval_repository.cache_clear()
    # Processors
    slack_processor.cache_clear()
    document_processor.cache_clear()
    # Config Managers
    slack_config_manager.cache_clear()
    # Connectors
    slack_connector.cache_clear()
    document_connector.cache_clear()
    # Chunkers
    slack_chunker.cache_clear()
    pdf_chunker.cache_clear()
    # Services
    pipeline_service.cache_clear()
    monitoring_service.cache_clear()
    data_source_service.cache_clear()
    terms_approval_service.cache_clear()
    # Registration & Dispatch
    doc_validators.cache_clear()
    slack_validators.cache_clear()
    registration_factory.cache_clear()
    registration_service.cache_clear()
    pipeline_dispatch_service.cache_clear()
    # Celery Adapters
    celery_pipeline_dispatcher.cache_clear()
    celery_slack_event_dispatcher.cache_clear()
    slack_event_dispatch_service.cache_clear()
    # Embedding
    embedding_generator.cache_clear()
    # Retrieval
    source_filter_resolver.cache_clear()
    retrieval_service.cache_clear()
    # Stats
    vector_stats_service.cache_clear()
    slack_stats_service.cache_clear()
    # Slack Events
    channel_created_handler.cache_clear()
    slack_event_service.cache_clear()
    # Pipeline Handlers & Executor
    slack_pipeline_handler.cache_clear()
    document_pipeline_handler.cache_clear()
    pipeline_executor.cache_clear()

