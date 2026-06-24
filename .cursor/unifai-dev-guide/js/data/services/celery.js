SERVICES.celery = {
  id: 'celery',
  name: 'RAG Celery Workers',
  icon: '⚡',
  role: 'Async ingestion pipelines',
  type: 'WORKER',
  x: -200, y: 570,
  w: 210, h: 60,
  detail: {
    subtitle: 'Celery • RabbitMQ broker • 3 queues',
    job: `
      <p><strong>Celery Workers</strong> handle all the heavy, long-running work for RAG: converting documents, generating embeddings, and indexing vectors. They run as separate processes to keep the API responsive.</p>
      <h3>Pipeline Flow</h3>
      <ul>
        <li><strong>1. Receive</strong> — task arrives from RabbitMQ queue</li>
        <li><strong>2. Convert</strong> — parse document (PDF, DOCX, etc.) into text via Docling</li>
        <li><strong>3. Chunk</strong> — split text into overlapping chunks (LangChain splitters)</li>
        <li><strong>4. Embed</strong> — generate vector embeddings (local or remote)</li>
        <li><strong>5. Index</strong> — upsert vectors + metadata into Qdrant</li>
      </ul>
      <h3>Three Queues</h3>
      <ul>
        <li><code>document_queue</code> — document ingestion pipelines</li>
        <li><code>slack_queue</code> — Slack channel ingestion pipelines</li>
        <li><code>slack_events_queue</code> — real-time Slack event processing</li>
      </ul>
    `,
    interfaces: `
      <h3>Celery Tasks</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">TASK</span><span class="path">execute_pipeline_task — runs full ingestion pipeline</span></div>
        <div class="endpoint"><span class="method post">TASK</span><span class="path">process_slack_events_task — handles Slack events (3 retries)</span></div>
      </div>
      <h3>Remote Services (when enabled)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">Docling: /v1/convert/file, /v1/convert/source</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">Embedding: /v1/embeddings (OpenAI-compatible)</span></div>
      </div>
    `,
    architecture: `
      <h3>Entry Point</h3>
      <p><code>rag/entrypoint.sh</code> with <code>ROLE=celery</code> runs:</p>
      <p><code>celery -A infrastructure.celery.app worker -Q $CELERY_QUEUES</code></p>
      <h3>Key Files</h3>
      <ul>
        <li><code>infrastructure/celery/app.py</code> — Celery app configuration</li>
        <li><code>infrastructure/celery/workers/pipeline_tasks.py</code> — pipeline execution task</li>
        <li><code>infrastructure/celery/workers/slack_event_tasks.py</code> — Slack event task</li>
        <li><code>infrastructure/celery/pipeline_dispatcher.py</code> — routes tasks to queues</li>
      </ul>
      <h3>Local vs Remote</h3>
      <p>Worker pool type depends on config: <code>threads</code> pool when using remote Docling/embedding, <code>solo</code> pool for local processing.</p>
    `,
    _endpoints: [
    { method: 'TASK', path: 'execute_pipeline_task', summary: 'runs full ingestion pipeline' },
    { method: 'TASK', path: 'process_slack_events_task', summary: 'handles Slack events (3 retries)' },
    { method: 'POST', path: 'Docling: /v1/convert/file, /v1/convert/source' },
    { method: 'POST', path: 'Embedding: /v1/embeddings (OpenAI-compatible)' },
  ],
  scheme: {
      nodes: [
        { id: 'rabbitmq', label: 'RabbitMQ', x: 15, y: 50, w: 72, h: 26, color: '#86EFAC' },
        { id: 'worker', label: 'Celery Worker', x: 140, y: 50, w: 85, h: 30, color: '#38BDF8' },
        { id: 'mongo', label: 'MongoDB', x: 280, y: 10, w: 72, h: 24, color: '#86EFAC' },
        { id: 'qdrant', label: 'Qdrant', x: 280, y: 40, w: 72, h: 24, color: '#86EFAC' },
        { id: 'docling', label: 'Docling', x: 280, y: 70, w: 72, h: 24, color: '#FBBF24' },
        { id: 'embed', label: 'Embed Svc', x: 280, y: 100, w: 72, h: 24, color: '#FBBF24' },
        { id: 'slack', label: 'Slack API', x: 280, y: 130, w: 72, h: 24, color: '#FBBF24' },
      ],
      edges: [
        { from: 'rabbitmq', to: 'worker', label: '3 queues' },
        { from: 'worker', to: 'mongo', label: 'metadata' },
        { from: 'worker', to: 'qdrant', label: 'upsert' },
        { from: 'worker', to: 'docling', label: 'convert' },
        { from: 'worker', to: 'embed', label: 'embed' },
        { from: 'worker', to: 'slack', label: 'fetch msgs' },
      ],
    },
  },
};
