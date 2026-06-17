SERVICES.global_utils = {
  id: 'global_utils',
  name: 'global_utils',
  icon: '📦',
  role: 'Shared lib (all backends)',
  type: 'SHARED',
  x: 600, y: 920,
  w: 230, h: 54,
  detail: {
    subtitle: 'Shared config, helpers, and clients — imported by all Python services',
    job: `
      <p><strong>global_utils</strong> is a shared Python package that lives in the monorepo at <code>global_utils/src/global_utils/</code>. It is <em>not</em> a running service — it's a library that every backend service imports as a dependency.</p>
      <h3>What It Provides</h3>
      <ul>
        <li><strong>SharedConfig</strong> — Pydantic-based config with connection strings for MongoDB, Redis, RabbitMQ, Temporal. Loads from env vars, .env files, YAML, and JSON.</li>
        <li><strong>Connection helpers</strong> — <code>get_mongo_url()</code>, <code>get_redis_url()</code>, <code>get_temporal_url()</code>, <code>get_rabbitmq_url()</code></li>
        <li><strong>DoclingClient / DoclingService</strong> — shared client for local or remote document conversion</li>
        <li><strong>EmbeddingClient / EmbeddingService</strong> — shared client for local or remote embedding generation</li>
        <li><strong>Celery app factory</strong> — shared Celery configuration and app creation</li>
        <li><strong>Flask helpers</strong> — common Flask setup used by all backend services</li>
        <li><strong>Utilities</strong> — logging config, file utils, async bridge, singleton pattern, JSON Schema validation</li>
      </ul>
      <h3>Who Uses It</h3>
      <p>Every Python service: RAG, Multi Agent System (MAS), Identity, Platform Backend, Celery Workers, and Temporal Workers. They all depend on <code>global_utils</code> in their <code>pyproject.toml</code>.</p>
    `,
    interfaces: `
      <h3>Key Exports</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">CFG</span><span class="path">SharedConfig — base config class with infra connection settings</span></div>
        <div class="endpoint"><span class="method get">FN</span><span class="path">get_mongo_url() — builds MongoDB connection string from config</span></div>
        <div class="endpoint"><span class="method get">FN</span><span class="path">get_redis_url() — builds Redis connection string</span></div>
        <div class="endpoint"><span class="method get">FN</span><span class="path">get_temporal_url() — builds Temporal gRPC address</span></div>
        <div class="endpoint"><span class="method get">FN</span><span class="path">get_rabbitmq_url() — builds AMQP broker URL</span></div>
        <div class="endpoint"><span class="method get">CLS</span><span class="path">DoclingClient / DoclingService — document conversion</span></div>
        <div class="endpoint"><span class="method get">CLS</span><span class="path">EmbeddingClient / EmbeddingService — embedding generation</span></div>
      </div>
    `,
    architecture: `
      <h3>Package Structure</h3>
      <ul>
        <li><code>config/</code> — <code>SharedConfig</code> (Pydantic BaseSettings), <code>ConfigManager</code>, multi-source loading (env, .env, YAML, JSON)</li>
        <li><code>utils/</code> — <code>get_mongo_url()</code>, <code>get_redis_url()</code>, logging config, singleton, async bridge, file utils</li>
        <li><code>redis/</code> — Redis client, <code>RedisKVStore</code>, server session management, session model, key constants (<code>identity:session:*</code>)</li>
        <li><code>ports/</code> — Abstract interfaces (e.g. <code>KVStore</code>) shared across services</li>
        <li><code>helpers/</code> — Pydantic helpers, API argument parsing</li>
        <li><code>docling/</code> — Docling client/service for document conversion</li>
        <li><code>embedding/</code> — Embedding client/service for vector generation</li>
        <li><code>celery_app/</code> — Shared Celery app factory and configuration</li>
        <li><code>flask/</code> — Common Flask setup helpers</li>
      </ul>
      <h3>How Services Use It</h3>
      <p>Each service extends <code>SharedConfig</code> with its own settings. For example, RAG's <code>AppConfig</code> adds <code>qdrant_ip</code>, <code>slack_bot_token</code>, etc. The base class provides all the shared infra connection settings.</p>
      <h3>Not a Deployed Service</h3>
      <p>This package is installed via <code>pip install -e</code> in development and bundled into each service's Docker image at build time. It has no CI/CD deployment of its own — it ships <em>inside</em> each service.</p>
    `,
    _endpoints: [
    { method: 'CFG', path: 'SharedConfig', summary: 'base config class with infra connection settings' },
    { method: 'FN', path: 'get_mongo_url()', summary: 'builds MongoDB connection string from config' },
    { method: 'FN', path: 'get_redis_url()', summary: 'builds Redis connection string' },
    { method: 'FN', path: 'get_temporal_url()', summary: 'builds Temporal gRPC address' },
    { method: 'FN', path: 'get_rabbitmq_url()', summary: 'builds AMQP broker URL' },
    { method: 'CLS', path: 'DoclingClient / DoclingService', summary: 'document conversion' },
    { method: 'CLS', path: 'EmbeddingClient / EmbeddingService', summary: 'embedding generation' },
  ],
  scheme: null,
  },
};
