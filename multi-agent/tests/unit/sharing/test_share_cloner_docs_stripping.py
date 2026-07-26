"""Unit test for docs stripping during docs_rag retriever cloning."""
from unittest.mock import MagicMock, create_autospec

from mas.sharing.cloner import ShareCloner, CloneContext, ResourceCacheData
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.blueprints.service import BlueprintService
from mas.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.core.enums import ResourceCategory
from mas.elements.retrievers.docs_rag.config import DocsRagRetrieverConfig


def _make_docs_rag_resource(docs=None, tags=None):
    """Build a docs_rag Resource with a populated config."""
    cfg = DocsRagRetrieverConfig(
        top_k_results=5,
        threshold=0.4,
        timeout=20.0,
        docs=docs,
        tags=tags,
    )
    return Resource(
        rid="original_rid",
        identity=Identity.user("alice"),
        category=ResourceCategory.RETRIEVER.value,
        type="docs_rag",
        name="My Retriever",
        cfg_dict=cfg.model_dump(mode="json"),
    )


class TestShareClonerDocsRagStripping:
    """Cloning a docs_rag retriever must strip sender's doc references."""

    def _build_cloner(self):
        registry = create_autospec(ResourcesRegistry, instance=True)
        registry.exists_by_name.return_value = False
        bp_service = create_autospec(BlueprintService, instance=True)
        element_registry = create_autospec(ElementRegistry, instance=True)
        element_registry.get_schema.return_value = DocsRagRetrieverConfig
        return ShareCloner(registry, bp_service, element_registry)

    def _build_cache_data(self, resource, cfg_model):
        return ResourceCacheData(
            doc=resource,
            dependencies=set(),
            cfg_model=cfg_model,
        )

    def test_docs_stripped_on_clone(self):
        """Sender's doc references must be removed from cloned config."""
        docs = [{"id": "d1", "name": "secret.pdf"}, {"id": "d2", "name": "internal.docx"}]
        resource = _make_docs_rag_resource(docs=docs)
        cfg_model = DocsRagRetrieverConfig(**resource.cfg_dict)

        cloner = self._build_cloner()
        ctx = CloneContext(sender_id="alice", recipient_id="bob")
        rid_mapping = {"original_rid": "new_rid_123"}

        result = cloner._clone_single_resource(
            self._build_cache_data(resource, cfg_model),
            rid_mapping,
            ctx,
        )

        assert result.cfg_dict["docs"] is None

    def test_other_config_fields_preserved(self):
        """Non-doc fields must survive the clone unchanged."""
        docs = [{"id": "d1", "name": "report.pdf"}]
        resource = _make_docs_rag_resource(docs=docs, tags=["finance", "q4"])
        cfg_model = DocsRagRetrieverConfig(**resource.cfg_dict)

        cloner = self._build_cloner()
        ctx = CloneContext(sender_id="alice", recipient_id="bob")
        rid_mapping = {"original_rid": "new_rid_456"}

        result = cloner._clone_single_resource(
            self._build_cache_data(resource, cfg_model),
            rid_mapping,
            ctx,
        )

        assert result.cfg_dict["top_k_results"] == 5
        assert result.cfg_dict["threshold"] == 0.4
        assert result.cfg_dict["timeout"] == 20.0
        assert result.cfg_dict["tags"] == ["finance", "q4"]

    def test_no_docs_field_unchanged(self):
        """Retriever with no docs should clone cleanly (no error)."""
        resource = _make_docs_rag_resource(docs=None)
        cfg_model = DocsRagRetrieverConfig(**resource.cfg_dict)

        cloner = self._build_cloner()
        ctx = CloneContext(sender_id="alice", recipient_id="bob")
        rid_mapping = {"original_rid": "new_rid_789"}

        result = cloner._clone_single_resource(
            self._build_cache_data(resource, cfg_model),
            rid_mapping,
            ctx,
        )

        assert result.cfg_dict["docs"] is None
