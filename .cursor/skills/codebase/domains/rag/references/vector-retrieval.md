# Vector Retrieval Component

Transforms processed documents into vector embeddings, stores in Qdrant, and serves semantic retrieval queries.

## Architecture

### Key Classes

| Class | File | Role |
|-------|------|------|
| `VectorRepository` (ABC) | `core/vector/domain/repository.py` | Port: init/store/search/count/delete vectors |
| `EmbeddingGenerator` (ABC) | `core/vector/domain/embedder.py` | Port: batch embed chunks and queries |
| `ContentChunker` (ABC) | `core/vector/domain/chunker.py` | Port: chunking strategy contract |
| `RetrievalService` | `core/retrieval/service.py` | Embed query + vector search with source filters |
| `VectorStatsService` | `core/vector/stats_service.py` | Qdrant chunk counts per collection |

### Adapter Implementations

| Port | Adapter | Tech |
|------|---------|------|
| `VectorRepository` | `QdrantVectorRepository` | Qdrant (HTTP) |
| `EmbeddingGenerator` | `DefaultEmbeddingGenerator` | Wraps `EmbeddingPort` |
| `EmbeddingPort` | `LocalEmbeddingAdapter` / `RemoteEmbeddingAdapter` | sentence-transformers / HTTP |
| `ContentChunker` | `PDFChunkerStrategy` / `SlackChunkerStrategy` | LangChain splitters |

### Qdrant Collections

| Collection | Source Type | Dimension |
|------------|-----------|-----------|
| `document_data` | DOCUMENT | 384 (configurable) |
| `slack_data` | SLACK | 384 (configurable) |

### Retrieval Flow

```
API endpoint (docs_bp / slack_bp) → RetrievalService
    → EmbeddingGenerator.generate_query_embedding(query)
    → VectorRepository.search(embedding, filters)
    → SourceFilterResolver (resolves source-specific filters)
    → Return ranked chunks with scores
```

## How to Extend

### Adding a New Chunking Strategy

1. Implement `ContentChunker` ABC in `infrastructure/sources/<type>/chunker.py`
2. Inject into the source-type pipeline handler
3. LangChain splitters are acceptable in infrastructure adapters (established pattern)

### Changing Embedding Model / Dimension

1. Update `embedding_dim` in `AppConfig`
2. Recreate or migrate Qdrant collections (dimension mismatch breaks search)
3. Switch adapter via `use_remote_embedding` + `EmbeddingPortFactory` if moving local ↔ remote

### Adding Source-Specific Search Filters

1. Extend `SourceFilterResolver` with filter composition for the source type
2. Wire collection selection in `RetrievalService` based on source type
3. Ensure Qdrant payload schema supports the new filter fields

## Cross-Component Contracts

### Vector → Infrastructure (Qdrant)

- `VectorRepository` → `QdrantVectorRepository` (`infrastructure/qdrant/qdrant_vector_repository.py`)
- Operations: collection lifecycle, upsert, search, filter delete
- Configuration: `qdrant_ip`, `qdrant_port` from `AppConfig`

### Vector → Infrastructure (Embedding)

- `EmbeddingPort` → `LocalEmbeddingAdapter` (SentenceTransformer in-process) or `RemoteEmbeddingAdapter` (HTTP /v1/embeddings)
- `DefaultEmbeddingGenerator` wraps `EmbeddingPort` with batching logic
- Adapter selection via `use_remote_embedding` config flag + `EmbeddingPortFactory`

### Vector ← Pipeline (ingestion path)

- `PipelineExecutor` calls pipeline handlers which use `EmbeddingGenerator` + `ContentChunker`
- `DocumentPipelineHandler`: Docling convert → `PDFChunkerStrategy` → `EmbeddingGenerator` → `VectorRepository.store()`
- `SlackPipelineHandler`: Slack fetch → process → `SlackChunkerStrategy` → `EmbeddingGenerator` → `VectorRepository.store()`

### Vector → API (retrieval path)

- `docs_bp` and `slack_bp` endpoints call `RetrievalService`
- `RetrievalService` uses `EmbeddingGenerator.generate_query_embedding()` then `VectorRepository.search()`
- `SourceFilterResolver` applies source-type-specific Qdrant filters

### Vector ← Data Sources (cleanup)

- `DataSourceService.delete()` calls `VectorRepository.delete()` to remove vectors when a source is deleted

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| `VectorRepository` port methods | QdrantVectorRepository, all callers | Single adapter implements the port |
| Embedding dimension | Qdrant collections, AppConfig, re-index pipelines | Dimension must match stored vectors |
| Qdrant payload schema | SourceFilterResolver, delete filters | Filters depend on payload fields |
| Chunker output format | Pipeline handlers, embedding batching | Handlers chain chunker → embedder |

## Boundaries

- **Depends on**: infrastructure (Qdrant client, embedding API clients)
- **Depended on by**: pipeline (stores vectors after processing), API (retrieval queries)
- **Ports**: `VectorRepository`, `EmbeddingGenerator`, `EmbeddingPort`, `ContentChunker`
