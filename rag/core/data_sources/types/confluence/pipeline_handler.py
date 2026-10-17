"""Confluence pipeline: incremental sync of a space or page subtree.

The source's type_data keeps a manifest {page_id: {version, title}} of what is
indexed. Each run lists the pages in scope and only fetches-and-embeds pages
that are new or whose version changed; the points of changed and vanished pages
are deleted before the new ones are stored (see stale_point_filters), so a run
over an unchanged space embeds nothing.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from typing import Any

from core.data_sources.service import DataSourceService
from core.pipeline.domain.port import PipelineContext, SourcePipelinePort
from core.vector.domain.embedder import EmbeddingGenerator
from core.vector.domain.model import VectorChunk
from infrastructure.sources.confluence.connector import (
    ConfluenceConnector,
    ConfluencePage,
)
from infrastructure.sources.confluence.html_text import html_to_text

logger = logging.getLogger("rag_pipeline")

POINT_NAMESPACE = uuid.UUID("0b1d6f7e-3a5c-4d2b-9f4e-7c8a2e1d5b60")


class ConfluencePipelineHandler(SourcePipelinePort):

    def __init__(self, connector_factory: Callable[[str], ConfluenceConnector], chunker: Any,
                 embedder: EmbeddingGenerator, data_source_service: DataSourceService) -> None:
        self._connector_factory = connector_factory
        self._chunker = chunker
        self._embedder = embedder
        self._sources = data_source_service
        self._manifest: dict[str, dict[str, Any]] = {}
        self._changed: list[ConfluencePage] = []
        self._deleted: list[str] = []
        self._unchanged = 0

    @property
    def source_type(self) -> str:
        return "CONFLUENCE"

    def _settings(self, context: PipelineContext) -> dict[str, Any]:
        source = self._sources.get_by_id(context.source_id)
        if source is None:
            raise ValueError(f"Confluence source {context.source_id} is not registered")
        return source.type_data or {}

    def collect(self, context: PipelineContext) -> list[ConfluencePage]:
        settings = self._settings(context)
        previous: dict[str, dict[str, Any]] = dict(settings.get("pages") or {})
        connector = self._connector_factory(settings["base_url"])
        live = list(connector.iter_pages(settings["space_key"], settings.get("root_title", ""),
                                         settings.get("exclude_labels", [])))
        self._manifest = {p.page_id: {"version": p.version, "title": p.title} for p in live}
        self._changed = [p for p in live if (previous.get(p.page_id) or {}).get("version") != p.version]
        self._deleted = sorted(set(previous) - set(self._manifest))
        self._unchanged = len(live) - len(self._changed)
        logger.info(f"Confluence {settings['space_key']}: {len(live)} pages, {len(self._changed)} new or changed, "
                    f"{len(self._deleted)} deleted, {self._unchanged} unchanged")
        return self._changed

    def process(self, context: PipelineContext, raw_data: list[ConfluencePage]) -> list[dict[str, Any]]:
        settings = self._settings(context)
        docs = []
        for page in raw_data:
            text = html_to_text(page.html)
            if not text:
                continue
            path = " / ".join(page.ancestors + [page.title])
            docs.append({
                "content": f"# {page.title}\n\n{text}",
                "filename": page.title,
                "page": page,
                "metadata": {"page_id": page.page_id, "title": page.title, "url": page.url,
                             "space_key": settings.get("space_key", ""), "path": path,
                             "version": page.version, "last_modified": page.last_modified},
            })
        return docs

    def chunk_and_embed(self, context: PipelineContext, processed: list[dict[str, Any]]) -> list[VectorChunk]:
        chunk_dicts: list[dict[str, Any]] = []
        for doc in processed:
            pieces = self._chunker.chunk_content([{"content": doc["content"], "filename": doc["filename"]}])
            for i, piece in enumerate(pieces):
                chunk_dicts.append({
                    "text": piece.get("text") or piece.get("content", ""),
                    "id": str(uuid.uuid5(POINT_NAMESPACE, f"{context.source_id}:{doc['metadata']['page_id']}:{i}")),
                    "metadata": {**doc["metadata"], "chunk_index": i, "source_id": context.source_id,
                                 "source_type": self.source_type, "owner_id": context.owner_id},
                })
        if not chunk_dicts:
            return []
        embedded = self._embedder.generate_embeddings(chunk_dicts)
        return [VectorChunk(text=d["text"], id=d["id"], metadata=d["metadata"],
                            embedding=d["embedding"].tolist() if hasattr(d["embedding"], "tolist") else d["embedding"])
                for d in embedded]

    def stale_point_filters(self, context: PipelineContext) -> list[dict[str, Any]]:
        """Points to delete before storing: every chunk of a changed or vanished page."""
        stale = [p.page_id for p in self._changed] + self._deleted
        if not stale:
            return []
        return [{"metadata.source_id": context.source_id, "metadata.page_id": stale}]

    def get_summary(self, context: PipelineContext, collected: Any) -> dict[str, Any]:
        return {"pages": self._manifest, "page_count": len(self._manifest), "pages_changed": len(self._changed),
                "pages_deleted": len(self._deleted), "pages_unchanged": self._unchanged}

    def cleanup(self, context: PipelineContext) -> bool:
        return True
