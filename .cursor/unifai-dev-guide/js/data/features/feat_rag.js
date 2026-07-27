FEATURES.feat_rag = {
  id: 'feat_rag',
  name: 'RAG Data Pipeline',
  icon: '📥',
  role: 'Ingest documents & search semantically',
  type: 'FEATURE',
  x: 940, y: -140,
  w: 270, h: 56,
  services: ['ui', 'rag', 'celery', 'rabbitmq', 'mongodb', 'qdrant'],
  detail: {
    subtitle: 'Upload → Convert → Chunk → Embed → Index → Search',
    job: `
      <p>The <strong>RAG Data Pipeline</strong> turns raw documents and Slack messages into searchable vector embeddings. It has two sides: <em>ingestion</em> (getting data in) and <em>retrieval</em> (searching it).</p>
      <h3>Ingestion</h3>
      <ul>
        <li>User uploads files (PDF, DOCX, etc.) or registers Slack channels</li>
        <li>RAG saves files and dispatches an async pipeline via Celery</li>
        <li>Workers convert documents, split into chunks, generate embeddings, and index to Qdrant</li>
      </ul>
      <h3>Retrieval</h3>
      <ul>
        <li>A search query is embedded and matched against Qdrant vectors</li>
        <li>Results include text chunks with metadata and relevance scores</li>
        <li>MAS agents use this via the <code>DocsRagRetriever</code> node type</li>
      </ul>
    `,
    interfaces: `
      <h3>Document Ingestion (UI → RAG /api1)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/upload — save files to disk</span></div>
        <div class="endpoint"><span class="method post">POST</span><span class="path">/docs/validate — check extensions & size</span></div>
        <div class="endpoint"><span class="method put">PUT</span><span class="path">/pipelines/embed — start ingestion pipeline</span></div>
      </div>
      <h3>Search (UI or MAS → RAG)</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/docs/query.match?query=&top_k_results=&docIds=&tags=</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/slack/query.match — same for Slack data</span></div>
      </div>
      <h3>Pipeline Status</h3>
      <div class="endpoint-list">
        <div class="endpoint"><span class="method get">GET</span><span class="path">/data_sources/data.sources.get — includes pipeline status</span></div>
        <div class="endpoint"><span class="method get">GET</span><span class="path">/vector/chunks.counts — Qdrant collection stats</span></div>
      </div>
    `,
    architecture: `
      <h3>Pipeline State Machine</h3>
      <p>Each pipeline goes through a fixed sequence of stages, managed by the <code>PipelineExecutor</code>:</p>
      <ul>
        <li><strong>COLLECTING</strong> — Get the raw content (parse PDF via Docling, or fetch Slack messages)</li>
        <li><strong>PROCESSING</strong> — Clean and normalize the text</li>
        <li><strong>CHUNKING_AND_EMBEDDING</strong> — Split into overlapping chunks, then generate vector embeddings</li>
        <li><strong>STORING</strong> — Batch-upsert vectors + metadata into Qdrant (100 points at a time)</li>
        <li><strong>DONE</strong> — Update pipeline status in MongoDB</li>
      </ul>
      <h3>Strategy Pattern for Different Sources</h3>
      <p>The pipeline uses different handlers depending on the data source type:</p>
      <ul>
        <li><code>DocumentPipelineHandler</code> — converts files via Docling, chunks via LangChain splitters</li>
        <li><code>SlackPipelineHandler</code> — fetches via Slack API, includes thread messages, chunks conversations</li>
      </ul>
      <p>Both handlers implement the same interface, so the executor doesn't care what the data source is.</p>
      <h3>Local vs Remote Processing</h3>
      <p>Both document conversion and embedding generation can run <strong>locally</strong> (in the worker process) or <strong>remotely</strong> (calling external services). This is configured per deployment — the code uses the same port interfaces either way.</p>
    `,
    flow: [
      { step: 1, label: 'User uploads documents', actor: 'UI → RAG', detail: 'Files (PDF, DOCX, etc.) are uploaded and saved to disk on the RAG server' },
      { step: 2, label: 'User triggers the embedding pipeline', actor: 'UI → RAG', detail: 'RAG registers the data source in MongoDB and queues an async task' },
      { step: 3, label: 'Task sent to the message queue', actor: 'RAG → RabbitMQ', detail: 'A Celery task message is placed on the <code>document_queue</code>' },
      { step: 4, label: 'Worker picks up the task', actor: 'Celery Worker', detail: 'The worker runs through a multi-stage pipeline automatically' },
      { step: 5, label: 'Convert → Chunk → Embed → Store', actor: 'Worker', detail: 'Parse the document to text, split into overlapping chunks, generate vector embeddings, and index them into Qdrant' },
      { step: 6, label: 'Pipeline marked complete', actor: 'Worker → MongoDB', detail: 'The pipeline status is updated so the UI can show progress/completion' },
      { step: 7, label: 'User searches documents', actor: 'UI → RAG → Qdrant', detail: 'A search query is embedded, matched against stored vectors, and the best-matching text chunks are returned' },
    ],
    codeFlow: [
      { step: 1, label: 'POST /docs/upload', actor: 'UI → RAG', detail: '<code>DocumentService.upload()</code> → <code>LocalFileStorage.save()</code> writes to disk' },
      { step: 2, label: 'PUT /pipelines/embed', actor: 'UI → RAG', detail: '<code>PipelineService.embed()</code> → <code>RegistrationService.register()</code> validates + persists <code>DataSource</code> in MongoDB' },
      { step: 3, label: 'CeleryPipelineDispatcher.dispatch()', actor: 'RAG → RabbitMQ', detail: 'Sends <code>execute_pipeline_task.delay()</code> to <code>document_queue</code>' },
      { step: 4, label: 'execute_pipeline_task()', actor: 'Celery Worker', detail: '<code>PipelineExecutor.execute(handler)</code> drives the state machine: COLLECTING → PROCESSING → CHUNKING → STORING → DONE' },
      { step: 5, label: 'DocumentPipelineHandler stages', actor: 'Worker', detail: '<code>DocumentConnector.process_document()</code> (Docling) → <code>PDFChunkerStrategy</code> (LangChain <code>RecursiveCharacterTextSplitter</code>) → <code>EmbeddingGenerator.generate_embeddings()</code>' },
      { step: 6, label: 'QdrantVectorRepository.store()', actor: 'Worker → Qdrant', detail: 'Batch upsert of 100 points with text + metadata payload; status updated in <code>pipeline_monitoring.pipelines</code>' },
      { step: 7, label: 'GET /docs/query.match', actor: 'UI → RAG → Qdrant', detail: '<code>RetrievalService.search()</code> → embed query via <code>EmbeddingGenerator</code> → <code>QdrantVectorRepository.search()</code> → return ranked chunks' },
    ],
      _endpoints: [
    { method: 'POST', path: '/docs/upload', summary: 'save files to disk' },
    { method: 'POST', path: '/docs/validate', summary: 'check extensions & size' },
    { method: 'PUT', path: '/pipelines/embed', summary: 'start ingestion pipeline' },
    { method: 'GET', path: '/docs/query.match?query=&top_k_results=&docIds=&tags=' },
    { method: 'GET', path: '/slack/query.match', summary: 'same for Slack data' },
    { method: 'GET', path: '/data_sources/data.sources.get', summary: 'includes pipeline status' },
    { method: 'GET', path: '/vector/chunks.counts', summary: 'Qdrant collection stats' },
  ],
  scheme: {
      nodes: [
        { id: 'ui', label: 'UI', x: 20, y: 55, w: 90, h: 36, color: '#BB86FC' },
        { id: 'rag', label: 'RAG', x: 180, y: 55, w: 110, h: 36, color: '#BB86FC' },
        { id: 'rabbit', label: 'RabbitMQ', x: 370, y: 55, w: 120, h: 36, color: '#86EFAC' },
        { id: 'celery', label: 'Celery Worker', x: 570, y: 55, w: 140, h: 36, color: '#38BDF8' },
        { id: 'qdrant', label: 'Qdrant', x: 790, y: 18, w: 100, h: 36, color: '#86EFAC' },
        { id: 'mongo', label: 'MongoDB', x: 790, y: 95, w: 120, h: 36, color: '#86EFAC' },
      ],
      edges: [
        { from: 'ui', to: 'rag', label: 'upload / query' },
        { from: 'rag', to: 'rabbit', label: 'dispatch task' },
        { from: 'rabbit', to: 'celery', label: 'consume' },
        { from: 'celery', to: 'qdrant', label: 'upsert vectors' },
        { from: 'celery', to: 'mongo', label: 'update status' },
      ],
    },
    dataModel: `
      <h3>MongoDB Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>pipeline_monitoring.data_sources</code>
          <p>Registered data sources (uploaded documents or Slack channels).</p>
          <div class="data-model-fields">Key fields: <code>userId</code>, <code>type</code> (document / slack), <code>files[]</code>, <code>status</code></div>
        </div>
        <div class="data-model-entry">
          <code>pipeline_monitoring.pipelines</code>
          <p>Pipeline execution tracking — status, stage progress, error info.</p>
          <div class="data-model-fields">Key fields: <code>dataSourceId</code>, <code>stage</code> (COLLECTING → DONE), <code>progress</code>, <code>error</code></div>
        </div>
      </div>
      <h3>Qdrant Collections</h3>
      <div class="data-model-section">
        <div class="data-model-entry">
          <code>document_data</code>
          <p>Vector embeddings for uploaded documents. Each point = one text chunk.</p>
          <div class="data-model-fields">Payload: <code>text</code>, <code>doc_id</code>, <code>file_name</code>, <code>chunk_index</code>, <code>metadata</code></div>
        </div>
        <div class="data-model-entry">
          <code>slack_data</code>
          <p>Vector embeddings for ingested Slack messages and threads.</p>
          <div class="data-model-fields">Payload: <code>text</code>, <code>channel_id</code>, <code>thread_ts</code>, <code>author</code>, <code>metadata</code></div>
        </div>
      </div>
    `,
    devScenarios: `
      <h3>Common Dev Tasks</h3>
      <div class="dev-scenario">
        <h4>Support a new document format</h4>
        <ol>
          <li>Add the extension to the allowed list in the validation endpoint</li>
          <li>If Docling doesn't support it natively, add a custom converter in <code>DocumentConnector</code></li>
          <li>The rest of the pipeline (chunking, embedding, storing) works unchanged</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Change the chunking strategy</h4>
        <ol>
          <li>Find the relevant <code>ChunkerStrategy</code> in the pipeline handlers</li>
          <li>LangChain's <code>RecursiveCharacterTextSplitter</code> is the default — swap or configure it</li>
          <li>Re-indexing existing documents requires re-running their pipelines</li>
        </ol>
      </div>
      <div class="dev-scenario">
        <h4>Debug a stuck pipeline</h4>
        <ol>
          <li>Check <code>pipeline_monitoring.pipelines</code> for the current stage and error</li>
          <li>Check Celery worker logs and RabbitMQ queue depth</li>
          <li>Pipelines are idempotent — re-triggering embed for the same data source is safe</li>
        </ol>
      </div>
    `,
    dependencies: {
      requires: [],
      requiredBy: [
        { featureId: 'feat_chats', reason: 'DocsRagRetriever nodes query RAG during session execution' },
        { featureId: 'feat_overview', reason: 'RAG Overview dashboard reads pipeline stats and chunk counts' },
      ],
    },
  },
};
