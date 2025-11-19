from abc import ABC, abstractmethod
from dataclasses import asdict
from utils.storage.vector_storage import VectorStorage
from utils.monitor.pipeline_monitor import PipelineMonitor
from utils.embedding.embedding_generator_factory import EmbeddingGeneratorFactory
from shared.config import EmbeddingConfig, StorageConfig
from utils.storage.vector_storage_factory import VectorStorageFactory
from typing import Any, Dict, Type
from functools import cached_property
from global_utils.utils.util import get_mongo_url
import pymongo
from .pipeline import Pipeline


class PipelineFactory(ABC):
    """
    Base factory that instantiates the five pipeline layers:
        1. orchestrator
        2. collector
        3. processor
        4. chunker and embedder
        5. storage

    Subclasses must implement each `_create_*` method.
    After construction, `self.collector`, `self.processor`, etc. are ready to use.
    """
    SOURCE_TYPE: str
    _registry: Dict[str, Type["PipelineFactory"]] = {} 
     
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if ABC not in cls.__bases__:
            PipelineFactory._registry[cls.SOURCE_TYPE] = cls
            
    @classmethod
    def create(cls, source_type: str) -> "PipelineFactory":
        try:
            factory_cls = cls._registry[source_type]
        except KeyError:
            raise ValueError(f"No PipelineFactory for {source_type!r}")
        return factory_cls()
    
    def __init__(self):
        pass
   
    @cached_property
    def vector_storage(self) -> VectorStorage:
        base_cfg = asdict(StorageConfig(collection_name=f"{self.SOURCE_TYPE.lower()}_data"))
        base_cfg["embedding_dim"] = self._create_embedder().embedding_dim
        vector_storage = VectorStorageFactory.create(base_cfg)
        vector_storage.initialize()
        return vector_storage
    
    def create_pipeline(self, metadata: Any) -> Pipeline:
        pipeline = Pipeline.create(self.SOURCE_TYPE)
        return pipeline(
            collector=self._create_collector(),
            processor=self._create_processor(),
            chunker=self._create_chunker(),
            embedder=self._create_embedder(),
            storage=self._create_storage(),
            monitor=self._create_monitor(),
            metadata=metadata
        )
    
    def _create_monitor(self) -> PipelineMonitor:
        return PipelineMonitor(pymongo.MongoClient(get_mongo_url()))
    
    @abstractmethod
    def _create_collector(self):
        """Return an instance of DataCollector"""
        ...

    @abstractmethod
    def _create_processor(self, data: Any):
        """Return an instance of your DataProcessor"""
        ...

    @abstractmethod
    def _create_chunker(self, processed: Any):
        """Return an instance of your Chunker strategy"""
        ...

    def _create_embedder(self) -> EmbeddingGeneratorFactory:
        cfg = EmbeddingConfig()
        return EmbeddingGeneratorFactory.create(asdict(cfg)) 
    
    def _create_storage(self) -> VectorStorage:
        """Create a vector storage instance"""
        return self.vector_storage
        
    