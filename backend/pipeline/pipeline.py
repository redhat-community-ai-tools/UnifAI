from abc import ABC, abstractmethod
from typing import Any, List, Dict, Type
from shared.logger import logger


class Pipeline(ABC):
    SOURCE_TYPE: str
    _registry: Dict[str, Type["Pipeline"]] = {}
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if ABC not in cls.__bases__:
            Pipeline._registry[cls.SOURCE_TYPE] = cls
            
    @classmethod
    def create(cls, source_type: str) -> "Pipeline":
        try:
            pipeline_cls = cls._registry[source_type]
        except KeyError:
            raise ValueError(f"No Pipeline for {source_type!r}")
        return pipeline_cls
    
    def __init__(
        self,
        collector,
        processor,
        chunker,
        embedder,
        storage,
        monitor=None,
        metadata=None,
    ):
        self.collector = collector
        self.processor = processor
        self.chunker = chunker
        self.embedder = embedder
        self.storage = storage
        self.monitor = monitor
        self.metadata = metadata

    def get_pipeline_id(self) -> str:
        return self.metadata.pipeline_id
    
    @abstractmethod
    def get_source_id(self) -> str:
        ...
    
    @abstractmethod
    def get_source_name(self) -> str:
        ...
    
    @abstractmethod
    def summary(self) -> Dict:
        ...
    
    def orchestration(self):
        self.monitor.start_log_monitoring(target_logger=logger, pipeline_id=f"{self.SOURCE_TYPE.lower()}_{self.get_source_id()}")
    
    @abstractmethod
    def collect_data(self):
        ...
    
    @abstractmethod
    def process_data(self, data: Any):
        ...
    
    @abstractmethod
    def chunk_and_embed(self, processed: Any):
        ...
    
    def store_embeddings(self, embeddings: List[Dict]):
        return self.storage.store_embeddings(embeddings)
    
    def clean_orchestration(self):
        self.monitor.finish_log_monitoring()
    
    def cleanup(self):
        """Override in subclasses that require cleanup (e.g., DocumentPipeline)."""
        return NotImplemented