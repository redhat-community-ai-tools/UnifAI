---
name: rag-vector-retrieval
scope: Embeddings, chunking, vector storage, and semantic search
parent: ../_index.md
when_to_load: Working on embeddings, chunking, Qdrant, or semantic retrieval in rag/
---

# RAG Vector Retrieval Component

Transforms processed documents into vector embeddings, stores in Qdrant, and serves semantic retrieval queries.

## Key Classes

| Class | File | Role |
|-------|------|------|
| `VectorRepository` (ABC) | `core/vector/domain/repository.py` | Port: init/store/search/count/delete vectors |
| `EmbeddingGenerator` (ABC) | `core/vector/domain/embedder.py` | Port: batch embed chunks and queries |
| `ContentChunker` (ABC) | `core/vector/domain/chunker.py` | Port: chunking strategy contract |
| `RetrievalService` | `core/retrieval/service.py` | Embed query + vector search with source filters |
| `VectorStatsService` | `core/vector/stats_service.py` | Qdrant chunk counts per collection |

## Adapter Implementations

| Port | Adapter | Tech |
|------|---------|------|
| `VectorRepository` | `QdrantVectorRepository` | Qdrant (HTTP) |
| `EmbeddingGenerator` | `DefaultEmbeddingGenerator` | Wraps `EmbeddingPort` |
| `EmbeddingPort` | `LocalEmbeddingAdapter` / `RemoteEmbeddingAdapter` | sentence-transformers / HTTP |
| `ContentChunker` | `PDFChunkerStrategy` / `SlackChunkerStrategy` | LangChain splitters |

## Qdrant Collections

| Collection | Source Type | Dimension |
|------------|-----------|-----------|
| `document_data` | DOCUMENT | 384 (configurable) |
| `slack_data` | SLACK | 384 (configurable) |

## Retrieval Flow

```
API endpoint (docs_bp / slack_bp) → RetrievalService
    → EmbeddingGenerator.generate_query_embedding(query)
    → VectorRepository.search(embedding, filters)
    → SourceFilterResolver (resolves source-specific filters)
    → Return ranked chunks with scores
```

## Boundaries

- **Depends on**: infrastructure (Qdrant client, embedding API clients)
- **Depended on by**: pipeline (stores vectors after processing), API (retrieval queries)
- **Ports**: `VectorRepository`, `EmbeddingGenerator`, `EmbeddingPort`, `ContentChunker`
