from functools import cached_property
from typing import Any
from pipeline.pipeline_factory import PipelineFactory
from pipeline.pipeline import Pipeline
from data_sources.docs.doc_config_manager import DocConfigManager
from data_sources.docs.doc_connector import DocumentConnector
from data_sources.docs.document_processor import DocumentProcessor
from data_sources.docs.pdf_chunker_strategy import PDFChunkerStrategy
from data_sources.docs.docs_validator import DocumentValidator
from shared.config import ChunkerConfig
from config.constants import DataSource

class DocumentPipelineFactory(PipelineFactory):
    SOURCE_TYPE = DataSource.DOCUMENT.upper_name
    def __init__(
        self,
    ):
        super().__init__()

    @cached_property
    def doc_config(self) -> DocConfigManager:
        config = DocConfigManager()
        config.set_config_value("chunk_size", ChunkerConfig.chunk_size)
        config.set_config_value("chunk_overlap", ChunkerConfig.chunk_overlap)
        return config

    def _create_collector(self) -> DocumentConnector:
        return DocumentConnector(self.doc_config)

    def _create_processor(self) -> DocumentProcessor:
        return DocumentProcessor()

    def _create_chunker(self) -> PDFChunkerStrategy:
        return PDFChunkerStrategy(
            max_tokens_per_chunk=self.doc_config._config["chunk_size"],
            overlap_tokens=self.doc_config._config["chunk_overlap"]
        )

    def _create_validator(self) -> DocumentValidator:
        return DocumentValidator()

    def create_pipeline(self, metadata: Any) -> Pipeline:
        pipeline_cls = Pipeline.create(self.SOURCE_TYPE)
        return pipeline_cls(
            collector=self._create_collector(),
            validator=self._create_validator(),
            processor=self._create_processor(),
            chunker=self._create_chunker(),
            embedder=self._create_embedder(),
            storage=self._create_storage(),
            monitor=self._create_monitor(),
            metadata=metadata,
        )
