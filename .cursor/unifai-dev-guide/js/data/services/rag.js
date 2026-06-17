SERVICES.rag = {
  id: 'rag',
  name: 'RAG',
  icon: '📄',
  role: 'Document & vector search',
  type: 'APP',
  x: 180, y: 380,
  w: 190, h: 60,
  detail: {
    subtitle: 'Flask • Port 13457 • Celery pipelines',
    modal: {
      job: `
        <p>The <strong>RAG</strong> is the data pipeline hub — documents, Slack channels, embeddings, and semantic search.</p>
        <h3>What It Does</h3>
        <ul>
          <li>Accepts document uploads and validates file types</li>
          <li>Manages Slack channel data sources</li>
          <li>Dispatches async ingestion pipelines via Celery</li>
          <li>Provides vector-based semantic search</li>
          <li>Tracks pipeline status, metrics, and errors</li>
        </ul>
        <h3>Who Calls It</h3>
        <ul>
          <li><strong>UI</strong> — via <code>/api1</code></li>
          <li><strong>Multi Agent System (MAS)</strong> — via <code>query.match</code> for retrieval</li>
          <li><strong>Platform Backend</strong> — via <code>ActionDispatcher</code></li>
          <li><strong>Slack</strong> — via Events API webhook</li>
        </ul>
      `,
      interfaces: `
        <h3>Document Operations</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/docs/upload</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/docs/query.match</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/docs/available.docs.get</span></div>
        </div>
        <h3>Slack & Data Sources</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/api/slack/fetch.available.slack.channels</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/api/slack/events</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/data_sources/data.sources.get</span></div>
        </div>
        <h3>Vector & Pipelines</h3>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/api/vector/chunks.counts</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/api/pipelines/embed</span></div>
        </div>
      `,
      architecture: `
        <h3>Design Pattern: Hexagonal Architecture</h3>
        <p>Business logic in <code>core/</code> talks through abstract ports. <code>infrastructure/</code> provides adapters. <code>bootstrap/</code> wires them.</p>
        <h3>Key Ports</h3>
        <ul>
          <li><code>VectorRepository</code> → Qdrant</li>
          <li><code>EmbeddingGenerator</code> → local or remote</li>
          <li><code>DocumentConverterPort</code> → local or remote Docling</li>
          <li><code>PipelineTaskDispatcher</code> → Celery</li>
          <li><code>PipelineRepository</code> → MongoDB</li>
        </ul>
      `,
    },
    job: `
      <p>The <strong>RAG</strong> (Retrieval-Augmented Generation) is the data pipeline hub of UnifAI. It manages the entire document lifecycle — uploading, validating, converting, chunking, embedding, indexing, and searching — across multiple data source types (documents and Slack channels).</p>

      <h3>Key Features</h3>
      <ul>
        <li><strong>Multi-source Ingestion</strong>: Document uploads (PDF, DOCX, HTML, etc.) and Slack channel messages, each with dedicated pipeline handlers.</li>
        <li><strong>Async Pipeline Execution</strong>: Heavy work (conversion, embedding, indexing) dispatched to Celery workers via RabbitMQ, keeping the API responsive.</li>
        <li><strong>Vector Semantic Search</strong>: Embeddings stored in Qdrant; <code>query.match</code> endpoint used by both UI and MAS agents for retrieval.</li>
        <li><strong>Source-Type Plugin Model</strong>: Each data source type (document, slack) has its own connector, chunker, validator, processor, and pipeline handler — all wired through a <code>RegistrationFactory</code>.</li>
        <li><strong>Local / Remote Adapter Switching</strong>: Docling (document conversion) and embedding generation can run locally (in-process) or remotely (HTTP), controlled by feature flags.</li>
        <li><strong>Pipeline Monitoring</strong>: Full metrics, error tracking, and log collection for every pipeline run.</li>
      </ul>

      <h3>Who Calls It</h3>
      <ul>
        <li><strong>UI</strong> — via <code>/api1</code> for all RAG dashboard operations (upload, embed, search, data source management)</li>
        <li><strong>Multi Agent System (MAS)</strong> — via <code>RagClient</code> for search queries (<code>query.match</code>) during agent execution</li>
        <li><strong>Platform Backend</strong> — via <code>ActionDispatcher</code> for config-triggered side-effects (e.g., Slack channel cleanup)</li>
        <li><strong>Slack</strong> — via Events API webhook at <code>POST /api/slack/events</code> for real-time channel updates</li>
      </ul>

      <h3>Ingestion Pipeline Flow</h3>
      <p>When a document is uploaded or a Slack channel is added:</p>
      <ul>
        <li><strong>1. Registration</strong> — validate source, check for duplicates, create metadata, build pipeline config</li>
        <li><strong>2. Dispatch</strong> — <code>PipelineTaskDispatcher</code> enqueues a Celery task to the appropriate queue (<code>document_queue</code> or <code>slack_queue</code>)</li>
        <li><strong>3. Collection</strong> — pipeline handler collects raw content (file bytes or Slack messages via API)</li>
        <li><strong>4. Processing</strong> — convert to text (Docling for documents, message formatting for Slack)</li>
        <li><strong>5. Chunking</strong> — split into overlapping chunks using source-specific strategies (PDF vs Slack thread chunkers)</li>
        <li><strong>6. Embedding</strong> — generate vector embeddings (local sentence-transformers or remote OpenAI-compatible API)</li>
        <li><strong>7. Indexing</strong> — upsert vectors + metadata into Qdrant collection (<code>document_data</code> or <code>slack_data</code>)</li>
        <li><strong>8. Status Update</strong> — persist pipeline status, metrics, and any errors to MongoDB</li>
      </ul>

      <h3>Domain Concepts</h3>
      <ul>
        <li><strong>Data Source</strong> — a registered content origin (a document file or Slack channel) with metadata and pipeline status.</li>
        <li><strong>Pipeline</strong> — a tracked execution of the ingestion flow for one data source, with status (PENDING → PROCESSING → COMPLETED/FAILED) and metrics.</li>
        <li><strong>Vector Collection</strong> — Qdrant collections per source type: <code>document_data</code>, <code>slack_data</code>.</li>
        <li><strong>Registration</strong> — the validation + metadata creation step before pipeline dispatch. Source-type specific via <code>RegistrationFactory</code>.</li>
        <li><strong>Terms Approval</strong> — user-level approval tracking for data usage terms.</li>
      </ul>

      <h3>14 Domain Services</h3>
      <ul>
        <li><code>DataSourceService</code> — CRUD + delete with vector cleanup</li>
        <li><code>DocumentService</code> — document-specific operations</li>
        <li><code>FileValidationService</code> — pre-upload validation (type, size, duplicates)</li>
        <li><code>RetrievalService</code> — vector search (query.match)</li>
        <li><code>PipelineService</code> — pipeline CRUD and status tracking</li>
        <li><code>PipelineDispatchService</code> — registration + Celery dispatch orchestration</li>
        <li><code>PipelineExecutor</code> — full pipeline lifecycle (collect → embed → store)</li>
        <li><code>RegistrationService</code> — source registration flows</li>
        <li><code>MonitoringService</code> — pipeline log/metrics orchestration</li>
        <li><code>VectorStatsService</code> — chunk count aggregation</li>
        <li><code>SlackEventService</code> — Slack event handler registry</li>
        <li><code>SlackEventDispatchService</code> — webhook → Celery dispatch</li>
        <li><code>SlackStatsService</code> — Slack aggregation stats</li>
        <li><code>ServicesHealthService</code> — external service readiness checks</li>
      </ul>
    `,
    interfaces: `
      <p>All routes under <code>/api/</code>. UI accesses via <code>/api1/</code> Nginx proxy. 8 Flask blueprints, 27 routes.</p>

      <details>
        <summary>Documents <span class="ep-count">6</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/upload — multipart file upload</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/validate — pre-upload validation</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/supported-extensions — allowed file types</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/available.docs.get — list documents</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/available.tags.get — document tags</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/query.match — semantic search</span></div>
        </div>
      </details>

      <details>
        <summary>Slack <span class="ep-count">7</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/slack/fetch.available.slack.channels — refresh from Slack API</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/available.slack.channels.get — cached channel list</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/slack.channel.chunks — chunk counts per channel</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/user.info.get — Slack user info</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/query.match — Slack semantic search</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/stats — Slack aggregation stats</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/slack/events — Slack Events API webhook</span></div>
        </div>
      </details>

      <details>
        <summary>Data Sources <span class="ep-count">4</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.sources.get — list all sources (paginated)</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.source.details.get — single source detail</span></div>
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/data_sources/data.source.update — update metadata</span></div>
          <div class="endpoint"><span class="method delete">DEL</span><span class="path">/data_sources/data.source.delete — delete + vector cleanup</span></div>
        </div>
      </details>

      <details>
        <summary>Pipelines & Vector <span class="ep-count">2</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method put">PUT</span><span class="path">/pipelines/embed — trigger embedding pipeline</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/vector/chunks.counts — chunk count per source</span></div>
        </div>
      </details>

      <details>
        <summary>Terms Approval <span class="ep-count">2</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/terms_approval/user.approval.status.get</span></div>
          <div class="endpoint"><span class="method post">POST</span><span class="path">/terms_approval/user.approval.record.post</span></div>
        </div>
      </details>

      <details>
        <summary>Settings & Health <span class="ep-count">4</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method get">GET</span><span class="path">/settings/get.umami.settings — analytics config</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/ — liveness</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/version</span></div>
          <div class="endpoint"><span class="method get">GET</span><span class="path">/health/service.readiness.get — external dep check</span></div>
        </div>
      </details>

      <details>
        <summary>Celery Tasks (via RabbitMQ) <span class="ep-count">2</span></summary>
        <div class="endpoint-list">
          <div class="endpoint"><span class="method post">TASK</span><span class="path">execute_pipeline_task — full ingestion pipeline (document_queue / slack_queue)</span></div>
          <div class="endpoint"><span class="method post">TASK</span><span class="path">process_slack_events_task — Slack event handling (slack_events_queue, 3 retries)</span></div>
        </div>
      </details>
    `,
    architecture: `
      <h3>Design Pattern: Hexagonal Architecture</h3>
      <p>RAG uses <strong>ports and adapters</strong>. Domain logic in <code>core/</code> (~104 Python files) defines ports (ABCs). <code>infrastructure/</code> (~59 files) provides adapters. <code>bootstrap/app_container.py</code> (~640 lines) wires ~40 singletons via <code>@lru_cache</code>.</p>

      <h3>Directory Layout</h3>
      <ul>
        <li><strong><code>core/</code></strong> — 13 bounded contexts: pipeline, data_sources (document + slack), vector/retrieval, monitoring, registration, health, validation, user/terms. ~104 Python files.</li>
        <li><strong><code>infrastructure/</code></strong> — Flask HTTP (8 blueprints), Celery workers, MongoDB repos, Qdrant, Slack API, Docling, Embedding adapters. ~59 files.</li>
        <li><strong><code>bootstrap/</code></strong> — <code>app_container.py</code> (composition root), <code>factories.py</code> (local vs remote adapter switching), <code>flask_app.py</code>.</li>
        <li><strong><code>config/</code></strong> — <code>AppConfig(SharedConfig)</code> with ~25 settings.</li>
      </ul>

      <h3>All 21 Port Abstractions</h3>
      <details>
        <summary>Repository Ports (7) <span class="ep-count">ABC</span></summary>
        <div class="endpoint-list">
          <p><code>VectorRepository</code> — store, search, delete embeddings (→ Qdrant)<br>
          <code>PipelineRepository</code> — pipeline CRUD, stats, status (→ MongoDB)<br>
          <code>DataSourceRepository</code> — source CRUD, pagination, distinct values (→ MongoDB)<br>
          <code>MonitoringRepository</code> — metrics, errors, logs (→ MongoDB)<br>
          <code>TermsApprovalRepository</code> — user approval tracking (→ MongoDB)<br>
          <code>SlackChannelRepository</code> — channel CRUD, membership (→ MongoDB)<br>
          <code>EmbeddingPort</code> — encode_texts, test_connection (→ local or remote)</p>
        </div>
      </details>
      <details>
        <summary>Service / Pipeline Ports (8) <span class="ep-count">ABC</span></summary>
        <div class="endpoint-list">
          <p><code>EmbeddingGenerator</code> — generate_embeddings, generate_query_embedding<br>
          <code>ContentChunker</code> — chunk_content, estimate_token_count<br>
          <code>SourcePipelinePort</code> — collect, process, chunk_and_embed, cleanup<br>
          <code>PipelineTaskDispatcher</code> — dispatch, dispatch_batch (→ Celery)<br>
          <code>RegistrationPort</code> — validate + register source<br>
          <code>SlackEventDispatcher</code> — dispatch events to Celery<br>
          <code>SlackEventHandler</code> — handle individual event types<br>
          <code>DocumentConverterPort</code> — convert_file, convert_url (→ Docling)</p>
        </div>
      </details>
      <details>
        <summary>Connector / Validation Ports (6) <span class="ep-count">Protocol</span></summary>
        <div class="endpoint-list">
          <p><code>DataConnector</code> — test_connection per source type<br>
          <code>DataProcessor</code> — process, clean_content<br>
          <code>DataSourceValidator</code> — validate source config<br>
          <code>HealthCheckable</code> — service readiness protocol<br>
          <code>BotInstallationCheckerPort</code> — Slack bot installation check<br>
          <code>DuplicateCheckerPort</code> — document duplicate detection</p>
        </div>
      </details>

      <h3>Port → Adapter Wiring</h3>
      <table class="info-table">
        <tr><th>Port</th><th>Adapter</th><th>Tech</th></tr>
        <tr><td><code>VectorRepository</code></td><td>QdrantVectorRepository</td><td>Qdrant</td></tr>
        <tr><td><code>PipelineRepository</code></td><td>MongoPipelineRepository</td><td>MongoDB</td></tr>
        <tr><td><code>DataSourceRepository</code></td><td>MongoDataSourceRepository</td><td>MongoDB</td></tr>
        <tr><td><code>MonitoringRepository</code></td><td>MongoMonitoringRepository</td><td>MongoDB</td></tr>
        <tr><td><code>SlackChannelRepository</code></td><td>MongoSlackChannelRepository</td><td>MongoDB</td></tr>
        <tr><td><code>TermsApprovalRepository</code></td><td>MongoTermsApprovalRepository</td><td>MongoDB</td></tr>
        <tr><td><code>EmbeddingPort</code></td><td>Local / RemoteEmbeddingAdapter</td><td>sentence-transformers / HTTP</td></tr>
        <tr><td><code>DocumentConverterPort</code></td><td>Local / RemoteDoclingAdapter</td><td>Docling / HTTP</td></tr>
        <tr><td><code>PipelineTaskDispatcher</code></td><td>CeleryPipelineDispatcher</td><td>RabbitMQ</td></tr>
        <tr><td><code>SlackEventDispatcher</code></td><td>CelerySlackEventDispatcher</td><td>RabbitMQ</td></tr>
        <tr><td><code>DataConnector</code></td><td>DocumentConnector / SlackConnector</td><td>Filesystem / Slack API</td></tr>
        <tr><td><code>ContentChunker</code></td><td>PDFChunkerStrategy / SlackChunkerStrategy</td><td>LangChain splitters</td></tr>
      </table>

      <h3>MongoDB (3 databases, 7+ collections)</h3>
      <table class="info-table">
        <tr><th>Database</th><th>Collection</th><th>Used By</th></tr>
        <tr><td>pipeline_monitoring</td><td>pipelines</td><td>MongoPipelineRepository</td></tr>
        <tr><td>pipeline_monitoring</td><td>metrics</td><td>MongoMonitoringRepository</td></tr>
        <tr><td>pipeline_monitoring</td><td>errors</td><td>MongoMonitoringRepository</td></tr>
        <tr><td>pipeline_monitoring</td><td>logs</td><td>MongoMonitoringRepository</td></tr>
        <tr><td>data_sources</td><td>sources</td><td>MongoDataSourceRepository</td></tr>
        <tr><td>data_sources</td><td>slack_channels</td><td>MongoSlackChannelRepository</td></tr>
        <tr><td>users</td><td>terms_user_approval</td><td>MongoTermsApprovalRepository</td></tr>
      </table>

      <h3>Qdrant Collections (vector store)</h3>
      <table class="info-table">
        <tr><th>Collection</th><th>Source Type</th></tr>
        <tr><td><code>document_data</code></td><td>DOCUMENT</td></tr>
        <tr><td><code>slack_data</code></td><td>SLACK</td></tr>
      </table>

      <h3>Source-Type Plugin Architecture</h3>
      <p>Each source type (document, slack) provides its own: <code>Connector</code>, <code>Processor</code>, <code>ChunkerStrategy</code>, <code>Validator(s)</code>, <code>PipelineHandler</code>, <code>Registration</code>, and <code>ConfigManager</code>. The <code>RegistrationFactory</code> and <code>get_pipeline_handler()</code> select the correct set based on source type.</p>

      <h3>Key Configuration (AppConfig)</h3>
      <table class="info-table">
        <tr><th>Setting</th><th>Default</th><th>Purpose</th></tr>
        <tr><td><code>port</code></td><td>13456</td><td>Flask server port</td></tr>
        <tr><td><code>use_remote_docling</code></td><td>false</td><td>Local vs remote document conversion</td></tr>
        <tr><td><code>use_remote_embedding</code></td><td>false</td><td>Local vs remote embedding generation</td></tr>
        <tr><td><code>qdrant_ip / qdrant_port</code></td><td>localhost:6333</td><td>Qdrant connection</td></tr>
        <tr><td><code>docling_service_url</code></td><td>(empty)</td><td>Remote Docling endpoint</td></tr>
        <tr><td><code>embedding_service_url</code></td><td>(empty)</td><td>Remote embedding endpoint</td></tr>
        <tr><td><code>embedding_dim</code></td><td>384</td><td>Vector dimension</td></tr>
        <tr><td><code>default_slack_bot_token</code></td><td>(empty)</td><td>Slack API token</td></tr>
      </table>
    `,
    _ports: [
    { name: 'VectorRepository', role: 'store, search, delete embeddings', adapter: 'Qdrant' },
    { name: 'PipelineRepository', role: 'pipeline CRUD, stats, status', adapter: 'MongoDB' },
    { name: 'DataSourceRepository', role: 'source CRUD, pagination, distinct values', adapter: 'MongoDB' },
    { name: 'MonitoringRepository', role: 'metrics, errors, logs', adapter: 'MongoDB' },
    { name: 'TermsApprovalRepository', role: 'user approval tracking', adapter: 'MongoDB' },
    { name: 'SlackChannelRepository', role: 'channel CRUD, membership', adapter: 'MongoDB' },
    { name: 'EmbeddingPort', role: 'encode_texts, test_connection', adapter: 'local or remote' },
    { name: 'EmbeddingGenerator', role: 'generate_embeddings, generate_query_embedding' },
    { name: 'ContentChunker', role: 'chunk_content, estimate_token_count' },
    { name: 'SourcePipelinePort', role: 'collect, process, chunk_and_embed, cleanup' },
    { name: 'PipelineTaskDispatcher', role: 'dispatch, dispatch_batch', adapter: 'Celery' },
    { name: 'RegistrationPort', role: 'validate + register source' },
    { name: 'SlackEventDispatcher', role: 'dispatch events to Celery' },
    { name: 'SlackEventHandler', role: 'handle individual event types' },
    { name: 'DocumentConverterPort', role: 'convert_file, convert_url', adapter: 'Docling' },
    { name: 'DataConnector', role: 'test_connection per source type' },
    { name: 'DataProcessor', role: 'process, clean_content' },
    { name: 'DataSourceValidator', role: 'validate source config' },
    { name: 'HealthCheckable', role: 'service readiness protocol' },
    { name: 'BotInstallationCheckerPort', role: 'Slack bot installation check' },
    { name: 'DuplicateCheckerPort', role: 'document duplicate detection' },
  ],
  _endpoints: [
    { method: 'POST', path: '/docs/upload', summary: 'multipart file upload', group: 'Documents' },
    { method: 'POST', path: '/docs/validate', summary: 'pre-upload validation', group: 'Documents' },
    { method: 'GET', path: '/docs/supported-extensions', summary: 'allowed file types', group: 'Documents' },
    { method: 'GET', path: '/docs/available.docs.get', summary: 'list documents', group: 'Documents' },
    { method: 'GET', path: '/docs/available.tags.get', summary: 'document tags', group: 'Documents' },
    { method: 'GET', path: '/docs/query.match', summary: 'semantic search', group: 'Documents' },
    { method: 'PUT', path: '/slack/fetch.available.slack.channels', summary: 'refresh from Slack API', group: 'Slack' },
    { method: 'GET', path: '/slack/available.slack.channels.get', summary: 'cached channel list', group: 'Slack' },
    { method: 'GET', path: '/slack/slack.channel.chunks', summary: 'chunk counts per channel', group: 'Slack' },
    { method: 'GET', path: '/slack/user.info.get', summary: 'Slack user info', group: 'Slack' },
    { method: 'GET', path: '/slack/query.match', summary: 'Slack semantic search', group: 'Slack' },
    { method: 'GET', path: '/slack/stats', summary: 'Slack aggregation stats', group: 'Slack' },
    { method: 'POST', path: '/slack/events', summary: 'Slack Events API webhook', group: 'Slack' },
    { method: 'GET', path: '/data_sources/data.sources.get', summary: 'list all sources (paginated)', group: 'Data Sources' },
    { method: 'GET', path: '/data_sources/data.source.details.get', summary: 'single source detail', group: 'Data Sources' },
    { method: 'PUT', path: '/data_sources/data.source.update', summary: 'update metadata', group: 'Data Sources' },
    { method: 'DEL', path: '/data_sources/data.source.delete', summary: 'delete + vector cleanup', group: 'Data Sources' },
    { method: 'PUT', path: '/pipelines/embed', summary: 'trigger embedding pipeline', group: 'Pipelines & Vector' },
    { method: 'GET', path: '/vector/chunks.counts', summary: 'chunk count per source', group: 'Pipelines & Vector' },
    { method: 'GET', path: '/terms_approval/user.approval.status.get', group: 'Terms Approval' },
    { method: 'POST', path: '/terms_approval/user.approval.record.post', group: 'Terms Approval' },
    { method: 'GET', path: '/settings/get.umami.settings', summary: 'analytics config', group: 'Settings & Health' },
    { method: 'GET', path: '/health/', summary: 'liveness', group: 'Settings & Health' },
    { method: 'GET', path: '/health/version', group: 'Settings & Health' },
    { method: 'GET', path: '/health/service.readiness.get', summary: 'external dep check', group: 'Settings & Health' },
    { method: 'TASK', path: 'execute_pipeline_task', summary: 'full ingestion pipeline (document_queue / slack_queue)', group: 'Celery Tasks (via RabbitMQ)' },
    { method: 'TASK', path: 'process_slack_events_task', summary: 'Slack event handling (slack_events_queue, 3 retries)', group: 'Celery Tasks (via RabbitMQ)' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI /api1', x: 20, y: 15, w: 100, h: 32, color: '#BB86FC' },
        { id: 'mas', label: 'Multi Agent System (MAS)', x: 20, y: 62, w: 100, h: 32, color: '#BB86FC' },
        { id: 'platform', label: 'Platform', x: 20, y: 109, w: 100, h: 32, color: '#BB86FC' },
        { id: 'slack_events', label: 'Slack Events', x: 20, y: 156, w: 115, h: 32, color: '#FBBF24' },
        { id: 'rag', label: 'RAG', x: 215, y: 82, w: 115, h: 38, color: '#BB86FC' },
        { id: 'rabbitmq', label: 'RabbitMQ', x: 420, y: 20, w: 110, h: 32, color: '#86EFAC' },
        { id: 'mongo', label: 'MongoDB', x: 420, y: 68, w: 100, h: 32, color: '#86EFAC' },
        { id: 'qdrant', label: 'Qdrant', x: 420, y: 116, w: 100, h: 32, color: '#86EFAC' },
        { id: 'slack_api', label: 'Slack API', x: 420, y: 164, w: 105, h: 32, color: '#FBBF24' },
      ],
      edges: [
        { from: 'ui', to: 'rag', label: 'HTTP' },
        { from: 'mas', to: 'rag', label: 'query.match' },
        { from: 'platform', to: 'rag', label: 'dispatch' },
        { from: 'slack_events', to: 'rag', label: 'webhook' },
        { from: 'rag', to: 'rabbitmq', label: 'enqueue' },
        { from: 'rag', to: 'mongo', label: 'read/write' },
        { from: 'rag', to: 'qdrant', label: 'search' },
        { from: 'rag', to: 'slack_api', label: 'fetch' },
      ],
    },
  },
};
