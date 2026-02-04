# RAG Flow Diagrams

> Visual guides showing how data flows through the feature-sliced architecture.

## Table of Contents

- [Document Pipeline Execution](#document-pipeline-execution)
- [Delete Data Source](#delete-data-source)
- [Search Flow](#search-flow)

---

## Document Pipeline Execution

Complete flow from file upload to vector storage.

```
═══════════════════════════════════════════════════════════════════════════════════════════════
                              DOCUMENT PIPELINE EXECUTION FLOW
═══════════════════════════════════════════════════════════════════════════════════════════════

 ┌─────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                    DRIVING ADAPTERS                                         │
 └─────────────────────────────────────────────────────────────────────────────────────────────┘

     ┌─────────┐                     ┌────────────────────────┐
     │   UI    │ POST /docs/upload   │ infrastructure/http/   │
     │ Client  │────────────────────▶│     docs.py            │   Saves files to disk
     └─────────┘                     └────────────────────────┘
          │
          │ POST /pipelines/embed
          ▼
     ┌────────────────────────┐
     │ infrastructure/http/   │
     │    pipelines.py        │
     └───────────┬────────────┘
                 │
 ════════════════╪══════════════════════════════════════════════════════════════════════════════
                 │                              CORE LAYER
 ════════════════╪══════════════════════════════════════════════════════════════════════════════
                 ▼
     ┌───────────────────────────────────┐
     │   PipelineDispatchService         │
     │   core/pipeline/dispatch_service  │
     └───────────┬───────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
 ┌──────────────┐  ┌─────────────────────┐
 │ Registration │  │  Task Dispatcher    │
 │   Service    │  │  (via Port)         │
 └──────┬───────┘  └──────────┬──────────┘
        │                     │
        │  • Validate files   │  dispatch_batch()
        │  • Create records   │       │
        │  • Save to MongoDB  │       ▼
        ▼                     │
 ┌──────────────────┐         │   ┌──────────────────────────────────────┐
 │ DocValidators    │         │   │  CeleryPipelineDispatcher            │
 │  • Extension     │         │   │  infrastructure/celery/              │
 │  • Size          │         └──▶│      pipeline_dispatcher.py          │
 │  • Duplicates    │             │                                      │
 └──────────────────┘             │  send_task("execute_pipeline_task")  │
                                  └──────────────────┬───────────────────┘
                                                     │
 ════════════════════════════════════════════════════╪══════════════════════════════════════════
                                                     │     CELERY WORKER (async)
 ════════════════════════════════════════════════════╪══════════════════════════════════════════
                                                     ▼
                              ┌───────────────────────────────────────────┐
                              │ infrastructure/celery/workers/            │
                              │        pipeline_tasks.py                  │
                              │                                           │
                              │  @CeleryApp().app.task                    │
                              │  def execute_pipeline_task(source_type,   │
                              │                            source_data):  │
                              └─────────────────┬─────────────────────────┘
                                                │
                                                │  build_context() → PipelineContext
                                                │  get_pipeline_handler("DOCUMENT")
                                                ▼
                              ┌───────────────────────────────────────────┐
                              │         PipelineExecutor                  │
                              │   core/pipeline/executor.py               │
                              └─────────────────┬─────────────────────────┘
                                                │
               ┌────────────────────────────────┼────────────────────────────────┐
               │                                │                                │
               ▼                                ▼                                ▼
    ┌────────────────────┐         ┌────────────────────┐           ┌────────────────────┐
    │   PipelineService  │         │  MonitoringService │           │  DataSourceService │
    │  register()        │         │  start_log()       │           │  upsert_after()    │
    │  update_status()   │         │  record_error()    │           │                    │
    └────────────────────┘         └────────────────────┘           └────────────────────┘
                                                │
 ═══════════════════════════════════════════════╪════════════════════════════════════════════════
                                                │            PIPELINE STEPS
 ═══════════════════════════════════════════════╪════════════════════════════════════════════════
                                                ▼
                              ┌───────────────────────────────────────────┐
                              │      DocumentPipelineHandler              │
                              │  core/data_sources/types/document/        │
                              │      pipeline_handler.py                  │
                              │  (implements SourcePipelinePort)          │
                              └─────────────────┬─────────────────────────┘
                                                │
          ┌─────────────────────────────────────┼─────────────────────────────────────┐
          │                                     │                                     │
          ▼                                     ▼                                     ▼
 ┌──────────────────┐              ┌──────────────────────┐              ┌──────────────────┐
 │  1. COLLECT      │              │   2. PROCESS         │              │  3. CHUNK &      │
 │                  │              │                      │              │     EMBED        │
 │  DocumentConnector──────────────▶ DocumentProcessor  ──────────────────▶ DocumentChunker │
 │  (load PDF/MD)   │              │  (extract text)      │              │  + Embedder      │
 └──────────────────┘              └──────────────────────┘              └────────┬─────────┘
                                                                                  │
                                                                                  ▼
 ═════════════════════════════════════════════════════════════════════════════════╪══════════════
                                                                                  │  DRIVEN ADAPTERS
 ═════════════════════════════════════════════════════════════════════════════════╪══════════════
                                                                                  ▼
                                                              ┌───────────────────────────────┐
                                                              │  4. STORE                     │
                                                              │                               │
                                                              │  QdrantVectorRepository       │
                                                              │  infrastructure/qdrant/       │
                                                              │                               │
                                                              │  vector_repo.store(chunks)    │
                                                              └───────────────┬───────────────┘
                                                                              │
                                                                              ▼
                                                                      ╔═══════════════╗
                                                                      ║    QDRANT     ║
                                                                      ║  Vector DB    ║
                                                                      ║               ║
                                                                      ║  384-dim      ║
                                                                      ║  embeddings   ║
                                                                      ╚═══════════════╝
```

---

## Delete Data Source

Shows the deletion cascade through vector storage and MongoDB with transaction-like behavior.

```
═══════════════════════════════════════════════════════════════════════════════════════════════
                              DELETE DATA SOURCE FLOW
═══════════════════════════════════════════════════════════════════════════════════════════════

     ┌─────────┐                     ┌────────────────────────┐
     │   UI    │ DELETE /data-sources│ infrastructure/http/   │
     │ Client  │────────────────────▶│   data_sources.py      │
     └─────────┘      /{source_id}   └───────────┬────────────┘
                                                 │
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 │                 CORE LAYER
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 ▼
                              ┌───────────────────────────────────────────┐
                              │         DataSourceService                 │
                              │   core/data_sources/service.py            │
                              │                                           │
                              │   def delete(source_id) -> DeleteResult   │
                              └─────────────────┬─────────────────────────┘
                                                │
                                                │  1. Find source by ID
                                                ▼
                              ┌───────────────────────────────────────────┐
                              │   source = source_repo.find_by_id()       │
                              │                                           │
                              │   if not source:                          │
                              │       return DeleteResult(success=False)  │
                              └─────────────────┬─────────────────────────┘
                                                │
 ═══════════════════════════════════════════════╪════════════════════════════════════════════════
                                                │       DELETION ORDER (Transaction-like)
 ═══════════════════════════════════════════════╪════════════════════════════════════════════════
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │                                               │
                        ▼                                               │
         ┌──────────────────────────────────┐                           │
         │  STEP 1: Delete Vector Embeddings │                          │
         │         (CRITICAL - abort if fails)                          │
         └──────────────────┬───────────────┘                           │
                            │                                           │
                            │  collection = f"{source_type}_data"       │
                            │  vector_repo = factory(collection)        │
                            ▼                                           │
                ┌─────────────────────────────────┐                     │
                │  QdrantVectorRepository         │                     │
                │  infrastructure/qdrant/         │                     │
                │                                 │                     │
                │  delete_by_source_id(source_id) │                     │
                └────────────────┬────────────────┘                     │
                                 │                                      │
                                 ▼                                      │
                         ╔═══════════════╗                              │
                         ║    QDRANT     ║                              │
                         ║               ║                              │
                         ║  DELETE WHERE ║                              │
                         ║  source_id =  ║                              │
                         ║  "source-123" ║                              │
                         ╚═══════════════╝                              │
                                 │                                      │
                                 │ vectors_deleted: int                 │
                                 ▼                                      │
         ┌───────────────────────────────────────────────────────────────
         │
         │  if vector deletion failed:
         │      return DeleteResult(
         │          success=False,
         │          message="Vector storage deletion failed"
         │      )
         │
         └───────────────────────┬───────────────────────────────────────
                                 │
                                 │  ✓ Vectors deleted successfully
                                 ▼
         ┌──────────────────────────────────┐
         │  STEP 2: Delete MongoDB Records  │
         │         (Pipeline + Source)      │
         └──────────────────┬───────────────┘
                            │
           ┌────────────────┴────────────────┐
           │                                 │
           ▼                                 ▼
┌─────────────────────────┐      ┌─────────────────────────┐
│ MongoPipelineRepository │      │ MongoDataSourceRepository│
│ infrastructure/mongo/   │      │ infrastructure/mongo/    │
│                         │      │                          │
│ delete(pipeline_id)     │      │ delete(source_id)        │
└───────────┬─────────────┘      └────────────┬─────────────┘
            │                                  │
            ▼                                  ▼
    ╔═══════════════╗                 ╔═══════════════╗
    ║   MONGODB     ║                 ║   MONGODB     ║
    ║               ║                 ║               ║
    ║  pipelines    ║                 ║   sources     ║
    ║  collection   ║                 ║  collection   ║
    ╚═══════════════╝                 ╚═══════════════╝
            │                                  │
            │ pipelines_deleted: int           │ source_deleted: bool
            │                                  │
            └────────────────┬─────────────────┘
                             │
                             ▼
         ┌───────────────────────────────────────────────────────────────
         │
         │  return DeleteResult(
         │      success=True,
         │      source_id="source-123",
         │      source_name="document.pdf",
         │      source_deleted=True,
         │      pipelines_deleted=1,
         │      vectors_deleted=150
         │  )
         │
         └───────────────────────────────────────────────────────────────

 ═══════════════════════════════════════════════════════════════════════════════════════════════
                                    RESPONSE TO CLIENT
 ═══════════════════════════════════════════════════════════════════════════════════════════════

    HTTP 200 OK
    {
        "success": true,
        "source_id": "source-123",
        "source_name": "document.pdf",
        "source_deleted": true,
        "pipelines_deleted": 1,
        "vectors_deleted": 150
    }
```

---

## Search Flow

Semantic search from query to results.

```
═══════════════════════════════════════════════════════════════════════════════════════════════
                                    SEARCH FLOW
═══════════════════════════════════════════════════════════════════════════════════════════════

     ┌─────────┐                     ┌────────────────────────┐
     │   UI    │  GET /docs/query    │ infrastructure/http/   │
     │ Client  │────────────────────▶│     docs.py            │
     └─────────┘   ?query=...        └───────────┬────────────┘
                   &top_k=5                      │
                   &doc_ids=[]                   │
                   &tags=[]                      │
                                                 │
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 │                 CORE LAYER
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 ▼
                              ┌───────────────────────────────────────────┐
                              │         RetrievalService                  │
                              │   core/retrieval/service.py               │
                              │                                           │
                              │   def search(query, limit, filters)       │
                              └─────────────────┬─────────────────────────┘
                                                │
               ┌────────────────────────────────┼────────────────────────────────┐
               │                                │                                │
               ▼                                ▼                                ▼
    ┌────────────────────┐         ┌────────────────────┐           ┌────────────────────┐
    │  1. RESOLVE        │         │  2. EMBED          │           │  3. SEARCH         │
    │     FILTERS        │         │     QUERY          │           │     VECTORS        │
    │                    │         │                    │           │                    │
    │  SourceFilter      │         │  EmbeddingGenerator│           │  VectorRepository  │
    │  Resolver          │         │  (384-dim)         │           │  .search()         │
    └────────┬───────────┘         └─────────┬──────────┘           └─────────┬──────────┘
             │                               │                                │
             │  doc_ids → source_ids         │  query → [0.1, 0.2, ...]       │
             │  tags → source_ids            │                                │
             ▼                               ▼                                ▼
 ════════════════════════════════════════════════════════════════════════════════════════════════
                                        DRIVEN ADAPTERS
 ════════════════════════════════════════════════════════════════════════════════════════════════

    ╔═══════════════╗           ╔═══════════════╗           ╔═══════════════╗
    ║   MONGODB     ║           ║  Sentence     ║           ║    QDRANT     ║
    ║               ║           ║  Transformer  ║           ║               ║
    ║  Lookup IDs   ║           ║               ║           ║  KNN Search   ║
    ║  by tags      ║           ║  all-MiniLM   ║           ║  top_k=5      ║
    ╚═══════════════╝           ╚═══════════════╝           ╚═══════════════╝
                                                                    │
                                                                    ▼
                                                     ┌──────────────────────────┐
                                                     │  SearchResult[]          │
                                                     │                          │
                                                     │  • text: "chunk content" │
                                                     │  • score: 0.89           │
                                                     │  • metadata: {...}       │
                                                     └──────────────────────────┘
                                                                    │
 ═══════════════════════════════════════════════════════════════════╪════════════════════════════
                                                                    │  RESPONSE
 ═══════════════════════════════════════════════════════════════════╪════════════════════════════
                                                                    ▼
                                                     HTTP 200 OK
                                                     {
                                                       "matches": [
                                                         {
                                                           "text": "...",
                                                           "score": 0.89,
                                                           "source_id": "...",
                                                           "filename": "doc.pdf"
                                                         },
                                                         ...
                                                       ]
                                                     }
```

---

## Slack Pipeline Execution

Flow for indexing Slack channel messages.

```
═══════════════════════════════════════════════════════════════════════════════════════════════
                              SLACK PIPELINE EXECUTION FLOW
═══════════════════════════════════════════════════════════════════════════════════════════════

     ┌─────────┐                     ┌────────────────────────┐
     │   UI    │ POST /slack/channels│ infrastructure/http/   │
     │ Client  │────────────────────▶│     slack.py           │
     └─────────┘                     └───────────┬────────────┘
                                                 │
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 │                 CORE LAYER
 ════════════════════════════════════════════════╪══════════════════════════════════════════════
                                                 ▼
                              ┌───────────────────────────────────────────┐
                              │   PipelineDispatchService                 │
                              │   core/pipeline/dispatch_service.py       │
                              └───────────┬───────────────────────────────┘
                                          │
                      ┌───────────────────┴───────────────────┐
                      │                                       │
                      ▼                                       ▼
               ┌──────────────────┐               ┌─────────────────────────┐
               │ SlackRegistration│               │ SlackValidators         │
               │ core/data_sources│               │ core/data_sources/types/│
               │ /types/slack/    │               │ slack/validators/       │
               │ registration.py  │               │ • bot installation      │
               └────────┬─────────┘               └─────────────────────────┘
                        │
                        │  Save channel to MongoDB
                        ▼
               ┌──────────────────────────┐
               │ MongoSlackChannelRepo    │
               │ infrastructure/mongo/    │
               │ data_sources/            │
               │ slack_channel_repository │
               └──────────────────────────┘
                        │
                        │  Dispatch async task
                        ▼
 ════════════════════════════════════════════════════════════════════════════════════════════════
                                    CELERY WORKER (async)
 ════════════════════════════════════════════════════════════════════════════════════════════════
                                          │
                                          ▼
                       ┌───────────────────────────────────────────┐
                       │      SlackPipelineHandler                 │
                       │  core/data_sources/types/slack/           │
                       │      pipeline_handler.py                  │
                       │  (implements SourcePipelinePort)          │
                       └─────────────────┬─────────────────────────┘
                                         │
          ┌──────────────────────────────┼──────────────────────────────┐
          │                              │                              │
          ▼                              ▼                              ▼
 ┌──────────────────┐       ┌──────────────────────┐       ┌──────────────────┐
 │  1. COLLECT      │       │   2. PROCESS         │       │  3. CHUNK &      │
 │                  │       │                      │       │     EMBED        │
 │  SlackConnector  │──────▶│  SlackProcessor     │──────▶│  SlackChunker    │
 │  + ThreadRetriever       │  (extract messages)  │       │  + Embedder      │
 └──────────────────┘       └──────────────────────┘       └────────┬─────────┘
                                                                    │
                                                                    ▼
                                                     ╔═══════════════════════════╗
                                                     ║  4. STORE → QDRANT        ║
                                                     ║  vector_repo.store()      ║
                                                     ╚═══════════════════════════╝
```

---

## Related Documentation

- [README.md](./README.md) — Main module documentation
