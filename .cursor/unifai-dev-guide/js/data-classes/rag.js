SERVICE_CLASSES.rag = {
  description: `<p>RAG follows <strong>hexagonal architecture</strong>: domain logic in <code>core/</code> defines ports (ABCs), <code>infrastructure/</code> provides adapters, and <code>bootstrap/</code> wires them together via <code>app_container</code> (lru_cache singletons).</p>`,
  layers: [
    {
      name: 'Bootstrap & Factories',
      classes: [
        { name: 'DocumentConverterFactory', file: 'bootstrap/factories.py', role: 'Builds local or remote Docling adapter based on config', calls: ['LocalDoclingAdapter', 'RemoteDoclingAdapter', 'global_utils:DoclingClient', 'global_utils:DoclingService'], calledBy: ['DocumentConnectorFactory'] },
        { name: 'DocumentConnectorFactory', file: 'bootstrap/factories.py', role: 'Builds DocumentConnector with chosen converter', calls: ['DocumentConverterFactory', 'DocumentConnector', 'DocConfigManager'], calledBy: ['AppContainer'] },
        { name: 'EmbeddingPortFactory', file: 'bootstrap/factories.py', role: 'Builds local or remote embedding adapter', calls: ['LocalEmbeddingAdapter', 'RemoteEmbeddingAdapter', 'global_utils:EmbeddingClient', 'global_utils:EmbeddingService'], calledBy: ['EmbeddingGeneratorFactory'] },
        { name: 'EmbeddingGeneratorFactory', file: 'bootstrap/factories.py', role: 'Wraps EmbeddingPort in DefaultEmbeddingGenerator', calls: ['DefaultEmbeddingGenerator', 'EmbeddingPortFactory'], calledBy: ['AppContainer'] },
        { name: 'VectorRepositoryFactory', file: 'bootstrap/factories.py', role: 'Builds QdrantVectorRepository from config', calls: ['QdrantVectorRepository', 'AppConfig'], calledBy: ['AppContainer'] },
      ]
    },
    {
      name: 'Core — Pipeline',
      classes: [
        { name: 'PipelineExecutor', file: 'core/pipeline/executor.py', role: 'Orchestrates pipeline stages: collect → process → chunk → embed → store', calls: ['PipelineService', 'MonitoringService', 'DataSourceService', 'VectorRepository', 'SourcePipelinePort'], calledBy: ['Celery: execute_pipeline_task'] },
        { name: 'PipelineService', file: 'core/pipeline/service.py', role: 'CRUD and status tracking for pipeline records', calls: ['PipelineRepository'], calledBy: ['PipelineExecutor', 'AppContainer'] },
        { name: 'PipelineDispatchService', file: 'core/pipeline/dispatch_service.py', role: 'Registers sources then dispatches batch tasks', calls: ['RegistrationService', 'PipelineTaskDispatcher'], calledBy: ['HTTP: /pipelines/embed'] },
        { name: 'SourcePipelinePort (ABC)', file: 'core/pipeline/domain/port.py', role: 'Port: collect/process/chunk_embed per source type', calls: [], calledBy: ['DocumentPipelineHandler', 'SlackPipelineHandler'] },
        { name: 'PipelineTaskDispatcher (ABC)', file: 'core/pipeline/domain/dispatcher.py', role: 'Port to enqueue async pipeline work', calls: [], calledBy: ['CeleryPipelineDispatcher'] },
        { name: 'PipelineRecord', file: 'core/pipeline/domain/model.py', role: 'Aggregate root for pipeline tracking (status, stats)', calls: [], calledBy: ['PipelineRepository', 'PipelineService', 'MonitoringService'] },
      ]
    },
    {
      name: 'Core — Data Sources & Registration',
      classes: [
        { name: 'DataSourceService', file: 'core/data_sources/service.py', role: 'CRUD, enrichment with pipeline stats, delete (vectors + mongo)', calls: ['DataSourceRepository', 'PipelineRepository', 'VectorRepository'], calledBy: ['PipelineExecutor', 'DocumentService', 'data_sources_bp'] },
        { name: 'RegistrationService', file: 'core/registration/service.py', role: 'Loops items through factory-created registrars', calls: ['RegistrationFactory'], calledBy: ['PipelineDispatchService'] },
        { name: 'RegistrationFactory', file: 'core/registration/factory.py', role: 'Chooses DocumentRegistration vs SlackRegistration', calls: ['DocumentRegistration', 'SlackRegistration', 'DataSourceRepository'], calledBy: ['RegistrationService'] },
        { name: 'DocumentRegistration', file: 'core/data_sources/types/document/registration.py', role: 'Validates and registers document sources', calls: ['BaseRegistration', 'Validator', 'DocValidators'], calledBy: ['RegistrationFactory'] },
        { name: 'SlackRegistration', file: 'core/data_sources/types/slack/registration.py', role: 'Validates and registers Slack channel sources', calls: ['BaseRegistration', 'Validator', 'SlackValidators'], calledBy: ['RegistrationFactory'] },
        { name: 'DocumentService', file: 'core/data_sources/types/document/document_service.py', role: 'DONE-only doc listing for UI', calls: ['DataSourceService'], calledBy: ['docs_bp'] },
        { name: 'FileValidationService', file: 'core/data_sources/types/document/file_validation_service.py', role: 'Pre-upload validation (extension, size, duplicates)', calls: ['DocConfigManager', 'NameDuplicateCheckerAdapter'], calledBy: ['docs_bp'] },
      ]
    },
    {
      name: 'Core — Vector & Retrieval',
      classes: [
        { name: 'VectorRepository (ABC)', file: 'core/vector/domain/repository.py', role: 'Port: init/store/search/count/delete vectors', calls: [], calledBy: ['QdrantVectorRepository', 'PipelineExecutor', 'DataSourceService', 'RetrievalService', 'VectorStatsService'] },
        { name: 'EmbeddingGenerator (ABC)', file: 'core/vector/domain/embedder.py', role: 'Port: batch embed chunks and queries', calls: [], calledBy: ['DefaultEmbeddingGenerator', 'DocumentPipelineHandler', 'SlackPipelineHandler', 'RetrievalService'] },
        { name: 'RetrievalService', file: 'core/retrieval/service.py', role: 'Embed query + vector search with source filters', calls: ['EmbeddingGenerator', 'VectorRepository', 'SourceFilterResolver'], calledBy: ['docs_bp', 'slack_bp'] },
        { name: 'VectorStatsService', file: 'core/vector/stats_service.py', role: 'Qdrant chunk counts per collection', calls: ['VectorRepository'], calledBy: ['vector_bp'] },
        { name: 'ContentChunker (ABC)', file: 'core/vector/domain/chunker.py', role: 'Chunking strategy contract', calls: [], calledBy: ['PDFChunkerStrategy', 'SlackChunkerStrategy'] },
      ]
    },
    {
      name: 'Core — Monitoring & Health',
      classes: [
        { name: 'MonitoringService', file: 'core/monitoring/service.py', role: 'Metrics, errors, logs capture via logging handler', calls: ['MonitoringRepository', 'PipelineRepository', 'LogParser'], calledBy: ['PipelineExecutor'] },
        { name: 'ServicesHealthService', file: 'core/health/service.py', role: 'Registry of HealthCheckable ports; check_all()', calls: ['HealthCheckable'], calledBy: ['health_bp'] },
        { name: 'LogParser', file: 'core/monitoring/parsing/base.py', role: 'Extracts chunk/embedding counts from log lines', calls: [], calledBy: ['MonitoringService'] },
      ]
    },
    {
      name: 'Core — Pipeline Handlers',
      classes: [
        { name: 'DocumentPipelineHandler', file: 'core/data_sources/types/document/pipeline_handler.py', role: 'SourcePipelinePort for documents: convert → chunk → embed', calls: ['DocumentConnector', 'DocumentProcessor', 'PDFChunkerStrategy', 'EmbeddingGenerator'], calledBy: ['PipelineExecutor'] },
        { name: 'SlackPipelineHandler', file: 'core/data_sources/types/slack/pipeline_handler.py', role: 'SourcePipelinePort for Slack: fetch → process → chunk → embed', calls: ['SlackConnector', 'SlackProcessor', 'SlackChunkerStrategy', 'EmbeddingGenerator'], calledBy: ['PipelineExecutor'] },
      ]
    },
    {
      name: 'Infrastructure — MongoDB',
      classes: [
        { name: 'MongoPipelineRepository', file: 'infrastructure/mongo/pipeline_repository.py', role: 'PipelineRepository adapter for pipelines collection', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoDataSourceRepository', file: 'infrastructure/mongo/data_source_repository.py', role: 'DataSourceRepository adapter with paginated queries', calls: ['PaginatedQueryBuilder'], calledBy: ['AppContainer'] },
        { name: 'MongoMonitoringRepository', file: 'infrastructure/mongo/monitoring_repository.py', role: 'MonitoringRepository adapter for metrics/errors/logs', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoSlackChannelRepository', file: 'infrastructure/mongo/data_sources/slack_channel_repository.py', role: 'SlackChannelRepository adapter', calls: ['PaginatedQueryBuilder'], calledBy: ['AppContainer'] },
        { name: 'PaginatedQueryBuilder', file: 'infrastructure/mongo/pagination_builder.py', role: 'Fluent Mongo aggregation for paged docs', calls: ['pymongo'], calledBy: ['MongoDataSourceRepository', 'MongoSlackChannelRepository'] },
      ]
    },
    {
      name: 'Infrastructure — Qdrant & Embedding',
      classes: [
        { name: 'QdrantVectorRepository', file: 'infrastructure/qdrant/qdrant_vector_repository.py', role: 'VectorRepository: collection lifecycle, upsert, search, filter delete', calls: ['qdrant_client'], calledBy: ['VectorRepositoryFactory'] },
        { name: 'DefaultEmbeddingGenerator', file: 'infrastructure/embedding/embedding_generator.py', role: 'Batched EmbeddingGenerator over EmbeddingPort', calls: ['EmbeddingPort'], calledBy: ['EmbeddingGeneratorFactory'] },
        { name: 'LocalEmbeddingAdapter', file: 'infrastructure/embedding/embedders/local_embedding_adapter.py', role: 'EmbeddingPort using SentenceTransformer locally', calls: ['sentence_transformers'], calledBy: ['EmbeddingPortFactory'] },
        { name: 'RemoteEmbeddingAdapter', file: 'infrastructure/embedding/embedders/remote_embedding_adapter.py', role: 'EmbeddingPort calling remote HTTP /v1/embeddings', calls: ['global_utils:EmbeddingService'], calledBy: ['EmbeddingPortFactory'] },
      ]
    },
    {
      name: 'Infrastructure — Celery & Sources',
      classes: [
        { name: 'CeleryPipelineDispatcher', file: 'infrastructure/celery/pipeline_dispatcher.py', role: 'PipelineTaskDispatcher via Celery send_task', calls: ['global_utils:send_task'], calledBy: ['AppContainer'] },
        { name: 'DocumentConnector', file: 'infrastructure/sources/document/connector.py', role: 'File → ProcessedDocument via converter', calls: ['DocumentConverterPort', 'DocConfigManager'], calledBy: ['DocumentPipelineHandler'] },
        { name: 'SlackConnector', file: 'infrastructure/sources/slack/connector.py', role: 'Slack Web API: history, caching, threads', calls: ['SlackConfigManager', 'SlackChannelRepository', 'SlackThreadRetriever'], calledBy: ['SlackPipelineHandler', 'slack_bp'] },
        { name: 'PDFChunkerStrategy', file: 'infrastructure/sources/document/chunker.py', role: 'ContentChunker using tiktoken + RecursiveCharacterTextSplitter', calls: ['langchain_splitters'], calledBy: ['DocumentPipelineHandler'] },
        { name: 'SlackChunkerStrategy', file: 'infrastructure/sources/slack/chunker.py', role: 'ContentChunker for Slack messages/threads', calls: ['langchain_splitters'], calledBy: ['SlackPipelineHandler'] },
        { name: 'LocalDoclingAdapter', file: 'infrastructure/sources/document/converters/local_docling_adapter.py', role: 'DocumentConverterPort using local docling library', calls: ['docling'], calledBy: ['DocumentConverterFactory'] },
        { name: 'RemoteDoclingAdapter', file: 'infrastructure/sources/document/converters/remote_docling_adapter.py', role: 'DocumentConverterPort calling remote Docling service', calls: ['global_utils:DoclingService'], calledBy: ['DocumentConverterFactory'] },
      ]
    },
    {
      name: 'Core — Slack Events',
      classes: [
        { name: 'SlackEventService', file: 'core/data_sources/types/slack/event_service.py', role: 'Registry of SlackEventHandler implementations; routes by event type', calls: ['SlackEventHandler'], calledBy: ['Celery: process_slack_events_task'] },
        { name: 'SlackEventDispatchService', file: 'core/data_sources/types/slack/event_dispatch_service.py', role: 'Validates webhook → dispatches to Celery via SlackEventDispatcher', calls: ['SlackEventDispatcher'], calledBy: ['slack_bp'] },
        { name: 'SlackStatsService', file: 'core/data_sources/types/slack/slack_stats_service.py', role: 'Aggregation stats: channel chunk counts, user info lookups', calls: ['VectorRepository', 'SlackChannelRepository'], calledBy: ['slack_bp'] },
        { name: 'CelerySlackEventDispatcher', file: 'infrastructure/celery/slack_event_dispatcher.py', role: 'SlackEventDispatcher adapter: enqueues to slack_events_queue', calls: ['global_utils:CeleryApp'], calledBy: ['SlackEventDispatchService'] },
      ]
    },
    {
      name: 'Core — Terms & Settings',
      classes: [
        { name: 'TermsApprovalService', file: 'core/terms_approval/service.py', role: 'User-level data usage approval tracking', calls: ['TermsApprovalRepository'], calledBy: ['terms_approval_bp'] },
        { name: 'MongoTermsApprovalRepository', file: 'infrastructure/mongo/terms_approval_repository.py', role: 'TermsApprovalRepository adapter for users.terms_user_approval', calls: ['pymongo'], calledBy: ['AppContainer'] },
      ]
    },
    {
      name: 'Infrastructure — Flask HTTP (8 Blueprints)',
      classes: [
        { name: 'docs_bp', file: 'infrastructure/flask/docs_routes.py', role: 'Upload, validate, list, search, tags, supported-extensions', calls: ['DocumentService', 'FileValidationService', 'RetrievalService', 'PipelineDispatchService'], calledBy: ['Flask: router'] },
        { name: 'slack_bp', file: 'infrastructure/flask/slack_routes.py', role: 'Channel fetch, list, chunks, user info, search, stats, events webhook', calls: ['SlackConnector', 'SlackStatsService', 'SlackEventDispatchService', 'RetrievalService'], calledBy: ['Flask: router'] },
        { name: 'data_sources_bp', file: 'infrastructure/flask/data_sources_routes.py', role: 'List, detail, update, delete with vector cleanup', calls: ['DataSourceService'], calledBy: ['Flask: router'] },
        { name: 'pipelines_bp', file: 'infrastructure/flask/pipelines_routes.py', role: 'Trigger embedding pipeline (dispatch)', calls: ['PipelineDispatchService'], calledBy: ['Flask: router'] },
        { name: 'vector_bp', file: 'infrastructure/flask/vector_routes.py', role: 'Chunk counts per source type', calls: ['VectorStatsService'], calledBy: ['Flask: router'] },
        { name: 'terms_approval_bp', file: 'infrastructure/flask/terms_approval_routes.py', role: 'Approval status check and record', calls: ['TermsApprovalService'], calledBy: ['Flask: router'] },
        { name: 'settings_bp', file: 'infrastructure/flask/settings_routes.py', role: 'Umami analytics settings', calls: ['AppConfig'], calledBy: ['Flask: router'] },
        { name: 'health_bp', file: 'infrastructure/flask/health_routes.py', role: 'Liveness, version, service readiness', calls: ['ServicesHealthService'], calledBy: ['Flask: router'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'http', label: 'Flask HTTP', x: 20, y: 15, w: 110, h: 34, color: '#BB86FC' },
      { id: 'dispatch', label: 'DispatchSvc', x: 20, y: 68, w: 115, h: 34, color: '#BB86FC' },
      { id: 'executor', label: 'PipelineExecutor', x: 215, y: 15, w: 150, h: 34, color: '#BB86FC' },
      { id: 'retrieval', label: 'RetrievalSvc', x: 215, y: 68, w: 135, h: 34, color: '#BB86FC' },
      { id: 'handler', label: 'PipelineHandler', x: 215, y: 121, w: 150, h: 34, color: '#BB86FC' },
      { id: 'mongo', label: 'Mongo Repos', x: 450, y: 15, w: 120, h: 34, color: '#86EFAC' },
      { id: 'qdrant', label: 'QdrantRepo', x: 450, y: 68, w: 115, h: 34, color: '#86EFAC' },
      { id: 'celery', label: 'CeleryDispatch', x: 450, y: 121, w: 135, h: 34, color: '#38BDF8' },
      { id: 'embed', label: 'EmbedGenerator', x: 450, y: 174, w: 140, h: 34, color: '#FBBF24' },
    ],
    edges: [
      { from: 'http', to: 'dispatch', label: 'embed' },
      { from: 'http', to: 'retrieval', label: 'search' },
      { from: 'dispatch', to: 'celery', label: 'enqueue' },
      { from: 'executor', to: 'handler', label: 'run stages' },
      { from: 'executor', to: 'mongo', label: 'status' },
      { from: 'handler', to: 'embed', label: 'vectors' },
      { from: 'handler', to: 'qdrant', label: 'store' },
      { from: 'retrieval', to: 'embed', label: 'query embed' },
      { from: 'retrieval', to: 'qdrant', label: 'search' },
    ],
  },
};
