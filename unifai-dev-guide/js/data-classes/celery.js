SERVICE_CLASSES.celery = {
  description: `<p>Celery Workers run inside the RAG codebase (<code>rag/infrastructure/celery/</code>). They consume tasks from RabbitMQ and drive the <code>PipelineExecutor</code> with source-specific handlers.</p>`,
  layers: [
    {
      name: 'Worker Entry',
      classes: [
        { name: 'CeleryApp (global_utils)', file: 'global_utils/celery_app/init.py', role: 'Celery application factory with RabbitMQ broker + Mongo backend', calls: ['global_utils:get_rabbitmq_url', 'global_utils:get_mongo_url'], calledBy: ['entrypoint'] },
        { name: 'execute_pipeline_task()', file: 'rag/infrastructure/celery/workers/pipeline_tasks.py', role: 'Task entry point: builds context, selects handler, calls PipelineExecutor', calls: ['rag:PipelineExecutor', 'rag:DocumentPipelineHandler', 'rag:SlackPipelineHandler'], calledBy: ['Celery: from RabbitMQ'] },
        { name: 'process_slack_events_task()', file: 'rag/infrastructure/celery/workers/slack_event_tasks.py', role: 'Task: dispatches Slack webhook events to handlers', calls: ['rag:SlackEventService'], calledBy: ['Celery: from slack_events_queue'] },
      ]
    },
    {
      name: 'Pipeline Execution (from RAG core)',
      classes: [
        { name: 'PipelineExecutor', file: 'rag/core/pipeline/executor.py', role: 'Drives pipeline stages: collect → process → chunk → embed → store', calls: ['rag:SourcePipelinePort', 'rag:PipelineService', 'rag:MonitoringService', 'rag:VectorRepository'], calledBy: ['execute_pipeline_task()'] },
        { name: 'DocumentPipelineHandler', file: 'rag/core/data_sources/types/document/pipeline_handler.py', role: 'SourcePipelinePort: Docling → chunk → embed for documents', calls: ['rag:DocumentConnector', 'rag:PDFChunkerStrategy', 'rag:EmbeddingGenerator'], calledBy: ['PipelineExecutor'] },
        { name: 'SlackPipelineHandler', file: 'rag/core/data_sources/types/slack/pipeline_handler.py', role: 'SourcePipelinePort: fetch Slack → process → chunk → embed', calls: ['rag:SlackConnector', 'rag:SlackChunkerStrategy', 'rag:EmbeddingGenerator'], calledBy: ['PipelineExecutor'] },
      ]
    },
    {
      name: 'External Service Calls',
      classes: [
        { name: 'LocalDoclingAdapter / RemoteDoclingAdapter', file: 'rag/infrastructure/sources/document/converters/', role: 'Document conversion (local library or remote HTTP)', calls: ['docling', 'global_utils:DoclingService'], calledBy: ['rag:DocumentConnector'] },
        { name: 'LocalEmbeddingAdapter / RemoteEmbeddingAdapter', file: 'rag/infrastructure/embedding/embedders/', role: 'Embedding generation (local SentenceTransformer or remote HTTP)', calls: ['sentence_transformers', 'global_utils:EmbeddingService'], calledBy: ['rag:DefaultEmbeddingGenerator'] },
        { name: 'QdrantVectorRepository', file: 'rag/infrastructure/qdrant/qdrant_vector_repository.py', role: 'Vector storage: upsert, search, delete in Qdrant', calls: ['qdrant_client'], calledBy: ['PipelineExecutor'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'rabbitmq', label: 'RabbitMQ', x: 20, y: 55, w: 110, h: 34, color: '#86EFAC' },
      { id: 'task', label: 'Celery Task', x: 200, y: 55, w: 115, h: 34, color: '#38BDF8' },
      { id: 'executor', label: 'PipelineExec', x: 390, y: 25, w: 130, h: 34, color: '#BB86FC' },
      { id: 'handler', label: 'Handler', x: 390, y: 85, w: 100, h: 34, color: '#BB86FC' },
      { id: 'qdrant', label: 'Qdrant', x: 590, y: 25, w: 95, h: 34, color: '#86EFAC' },
      { id: 'docling', label: 'Docling', x: 590, y: 85, w: 95, h: 34, color: '#FBBF24' },
    ],
    edges: [
      { from: 'rabbitmq', to: 'task', label: 'consume' },
      { from: 'task', to: 'executor', label: 'run' },
      { from: 'executor', to: 'handler', label: 'stages' },
      { from: 'handler', to: 'qdrant', label: 'store' },
      { from: 'handler', to: 'docling', label: 'convert' },
    ],
  },
};
