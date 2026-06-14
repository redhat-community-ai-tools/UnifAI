---
name: rag-vector-relationships
scope: Cross-component contracts for vector retrieval
parent: _index.md
---

# Vector Retrieval Relationships

## Vector → Infrastructure (Qdrant)

- `VectorRepository` → `QdrantVectorRepository` (`infrastructure/qdrant/qdrant_vector_repository.py`)
- Operations: collection lifecycle, upsert, search, filter delete
- Configuration: `qdrant_ip`, `qdrant_port` from `AppConfig`

## Vector → Infrastructure (Embedding)

- `EmbeddingPort` → `LocalEmbeddingAdapter` (SentenceTransformer in-process) or `RemoteEmbeddingAdapter` (HTTP /v1/embeddings)
- `DefaultEmbeddingGenerator` wraps `EmbeddingPort` with batching logic
- Adapter selection via `use_remote_embedding` config flag + `EmbeddingPortFactory`

## Vector ← Pipeline (ingestion path)

- `PipelineExecutor` calls pipeline handlers which use `EmbeddingGenerator` + `ContentChunker`
- `DocumentPipelineHandler`: Docling convert → `PDFChunkerStrategy` → `EmbeddingGenerator` → `VectorRepository.store()`
- `SlackPipelineHandler`: Slack fetch → process → `SlackChunkerStrategy` → `EmbeddingGenerator` → `VectorRepository.store()`

## Vector → API (retrieval path)

- `docs_bp` and `slack_bp` endpoints call `RetrievalService`
- `RetrievalService` uses `EmbeddingGenerator.generate_query_embedding()` then `VectorRepository.search()`
- `SourceFilterResolver` applies source-type-specific Qdrant filters

## Vector ← Data Sources (cleanup)

- `DataSourceService.delete()` calls `VectorRepository.delete()` to remove vectors when a source is deleted
