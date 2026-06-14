---
name: rag-knowledge
description: >-
  Hierarchical knowledge system for the RAG (Retrieval-Augmented Generation) service.
  Provides architectural navigation, component routing, and RAG-specific rules.
  Use when working on any file under rag/ — start by reading _index.md to identify
  which component your task involves.
paths: rag/**
---

# RAG Knowledge System

## How to Use

1. **Read `_index.md`** — identify which component(s) your task involves
2. **Load component directory** — read `<component>/_index.md` for architecture and patterns
3. **If crossing components** — read `<component>/relationships.md` for contracts and flow
4. **Before writing code** — read `rules.md` for RAG-specific enforcement
5. **Always** — load `../../architecture/standards.md` for universal rules

## Structure

```
rag/
├── SKILL.md                Cursor discovery metadata (this file)
├── _index.md               Navigation, routing table, service map
├── rules.md                RAG-specific architectural rules
├── pipeline/
│   ├── _index.md           Pipeline execution, dispatch, status tracking
│   └── relationships.md    → data-sources, → infrastructure
├── data-sources/
│   ├── _index.md           Source types, plugin model, connectors
│   └── relationships.md    → pipeline (registration), → infrastructure (storage)
├── vector-retrieval/
│   ├── _index.md           Embeddings, chunking, Qdrant, query
│   └── relationships.md    → pipeline (ingestion), → infrastructure (Qdrant client)
├── infrastructure/
│   ├── _index.md           Flask, Mongo, Qdrant, Celery, connectors
│   └── relationships.md    Port-adapter mapping
└── bootstrap/
    └── _index.md           App container, factories, config
```

## Companion Skills

- `../../architecture/standards.md` — Universal coding rules
- `../multi-agent/SKILL.md` — MAS domain (cross-service integration)
