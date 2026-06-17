SERVICE_CLASSES.global_utils = {
  description: `<p><code>global_utils</code> is a shared library installed in every Python service. It provides config, Redis session management, async bridging, embedding/docling HTTP clients, Celery factories, and Flask helpers.</p>`,
  layers: [
    {
      name: 'Config',
      classes: [
        { name: 'SharedConfig', file: 'config/config.py', role: 'Pydantic BaseSettings singleton: MongoDB, RabbitMQ, Temporal, Redis fields', calls: ['DotEnvSource', 'YamlSource', 'JsonSource'], calledBy: ['rag:AppConfig', 'mas:AppConfig', 'identity:AppConfig', 'platform:AppConfig'] },
        { name: 'ConfigManager', file: 'config/manager.py', role: 'JSON file-backed singleton config with env substitution', calls: [], calledBy: [] },
        { name: 'ConfigSource (ABC)', file: 'config/sources.py', role: 'Abstract load() → dict for pluggable settings sources', calls: [], calledBy: ['DotEnvSource', 'YamlSource', 'JsonSource'] },
      ]
    },
    {
      name: 'Redis & Ports',
      classes: [
        { name: 'KVStore (ABC)', file: 'ports/kv_store.py', role: 'Hexagonal port for string key-value operations with TTL', calls: [], calledBy: ['RedisKVStore'] },
        { name: 'RedisKVStore', file: 'redis/redis_kv_store.py', role: 'Adapter: implements KVStore + hash helpers for identity sessions', calls: ['redis', 'KVStore'], calledBy: ['identity:AuthManager', 'identity:build_auth_stack'] },
        { name: 'build_redis_client()', file: 'redis/client.py', role: 'Memoized redis.Redis factory from SharedConfig', calls: ['SharedConfig', 'redis'], calledBy: ['identity:build_auth_stack'] },
        { name: 'UserSessionData', file: 'redis/session_model.py', role: 'Pydantic model for identity Redis hash (tokens, user, expiry)', calls: [], calledBy: ['get_identity_session()'] },
        { name: 'get_identity_session()', file: 'redis/server_session.py', role: 'Read identity hash → UserSessionData', calls: ['identity_session_key', 'UserSessionData'], calledBy: ['require_identity_session()'] },
      ]
    },
    {
      name: 'Utilities',
      classes: [
        { name: 'SingletonMeta', file: 'utils/singleton.py', role: 'Metaclass implementing per-process single instance', calls: [], calledBy: ['mas:AppContainer', 'mas:ElementRegistry', 'AsyncBridge'] },
        { name: 'AsyncBridge', file: 'utils/async_bridge.py', role: 'Process-wide anyio BlockingPortal to run async from sync', calls: ['anyio', 'threading'], calledBy: ['mas:McpProvider', 'mas:A2AAgentNode', 'mas:CustomAgentNode'] },
        { name: 'get_mongo_url()', file: 'utils/util.py', role: 'Build MongoDB connection URL from SharedConfig', calls: ['SharedConfig'], calledBy: ['rag:AppContainer', 'mas:AppContainer', 'identity:create_app()', 'platform:AppContainer', 'CeleryApp'] },
        { name: 'get_redis_url()', file: 'utils/util.py', role: 'Build Redis connection URL', calls: ['SharedConfig'], calledBy: ['mas:AppContainer', 'identity:build_auth_stack'] },
        { name: 'get_rabbitmq_url()', file: 'utils/util.py', role: 'Build AMQP broker URL', calls: ['SharedConfig'], calledBy: ['rag:CeleryPipelineDispatcher', 'CeleryApp'] },
        { name: 'json_schema_model()', file: 'utils/util.py', role: 'Generate Pydantic model from JSON Schema at runtime', calls: ['datamodel_code_generator'], calledBy: ['mas:BaseElementSpec'] },
      ]
    },
    {
      name: 'Docling & Embedding Clients',
      classes: [
        { name: 'DoclingClient', file: 'docling/client.py', role: 'Sync httpx transport: async job submit/poll/fetch for document conversion', calls: ['httpx'], calledBy: ['DoclingService'] },
        { name: 'DoclingService', file: 'docling/service.py', role: 'Validates inputs, calls client, validates response', calls: ['DoclingClient'], calledBy: ['rag:RemoteDoclingAdapter'] },
        { name: 'EmbeddingClient', file: 'embedding/client.py', role: 'httpx POST /v1/embeddings with truncate flag', calls: ['httpx'], calledBy: ['EmbeddingService'] },
        { name: 'EmbeddingService', file: 'embedding/service.py', role: 'Validates text list, maps response to vectors', calls: ['EmbeddingClient'], calledBy: ['rag:RemoteEmbeddingAdapter'] },
      ]
    },
    {
      name: 'Celery & Flask',
      classes: [
        { name: 'CeleryApp', file: 'celery_app/init.py', role: 'Singleton wrapping celery.Celery: RabbitMQ broker, Mongo backend', calls: ['get_mongo_url()', 'get_rabbitmq_url()'], calledBy: ['rag:CeleryPipelineDispatcher', 'celery:execute_pipeline_task'] },
        { name: 'send_task()', file: 'celery_app/helpers.py', role: 'Send named task to Celery queue', calls: ['CeleryApp'], calledBy: ['rag:CeleryPipelineDispatcher'] },
        { name: 'RequestRules', file: 'flask/request_rules.py', role: 'Flask before/after request hooks (size cap, headers)', calls: [], calledBy: ['rag:AppContainer', 'mas:AppContainer', 'identity:create_app()', 'platform:AppContainer'] },
        { name: 'require_identity_session()', file: 'flask/decorators.py', role: 'Decorator: validates identity session from Redis', calls: ['get_identity_session()'], calledBy: ['platform:health_bp'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'services', label: 'All Services', x: 20, y: 62, w: 115, h: 34, color: '#BB86FC' },
      { id: 'config', label: 'SharedConfig', x: 205, y: 15, w: 130, h: 34, color: '#A78BFA' },
      { id: 'redis_mod', label: 'Redis Module', x: 205, y: 68, w: 130, h: 34, color: '#86EFAC' },
      { id: 'utils', label: 'Utils', x: 205, y: 121, w: 95, h: 34, color: '#A78BFA' },
      { id: 'docling', label: 'Docling', x: 415, y: 15, w: 100, h: 34, color: '#FBBF24' },
      { id: 'embedding', label: 'Embedding', x: 415, y: 68, w: 110, h: 34, color: '#FBBF24' },
      { id: 'celery', label: 'CeleryApp', x: 415, y: 121, w: 110, h: 34, color: '#38BDF8' },
    ],
    edges: [
      { from: 'services', to: 'config', label: 'extend' },
      { from: 'services', to: 'redis_mod', label: 'sessions' },
      { from: 'services', to: 'utils', label: 'URLs, async' },
      { from: 'utils', to: 'docling', label: 'HTTP client' },
      { from: 'utils', to: 'embedding', label: 'HTTP client' },
      { from: 'utils', to: 'celery', label: 'broker' },
    ],
  },
};
