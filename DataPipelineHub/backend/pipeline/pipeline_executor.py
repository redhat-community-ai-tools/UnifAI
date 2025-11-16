from typing import Any
from pipeline.pipeline_repository import PipelineRepository
from config.constants import PipelineStatus
from pipeline.decorators import pipeline_step
from pipeline.pipeline_factory import Pipeline

class PipelineExecutor:
    """
    Given a PipelineFactory (with its five steps already created),
    .run() will invoke:
      1. orchestrator()
      2. collector()
      3. processor(collected)
      4. chunker_and_embedder(processed)
      5. storage(embeddings)
    and return whatever the storage step produces.
    """
    def __init__(
        self,
        pipeline: Pipeline,
        repo: PipelineRepository
    ):
        self.pipeline     = pipeline
        self.repo         = repo
        self.repo.register_pipeline(pipeline)
        
    def _run_orchestration(self):
        return self.pipeline.orchestration()

    @pipeline_step(PipelineStatus.COLLECTING.value)
    def _run_collect(self):
        return self.pipeline.collect_data()

    @pipeline_step(PipelineStatus.PROCESSING.value)
    def _run_process(
        self,
        collected: Any
    ) -> Any:
        return self.pipeline.process_data(collected)

    @pipeline_step(PipelineStatus.CHUNKING_AND_EMBEDDING.value)
    def _run_chunk_and_embed(
        self,
        processed: Any
    ) -> Any:
        return self.pipeline.chunk_and_embed(processed)

    @pipeline_step(PipelineStatus.STORING.value)
    def _run_store(
        self,
        embeddings: Any
    ) -> Any:
        return self.pipeline.store_embeddings(embeddings)

    def _run_clean_orchestration(self):
        self.pipeline.clean_orchestration()

    def run(self) -> Any:
        self._run_orchestration()
        stored = None
        try:
            collected   = self._run_collect()
            processed   = self._run_process(collected)
            embeddings  = self._run_chunk_and_embed(processed)
            stored      = self._run_store(embeddings)
            self.repo.update_pipeline_status(
                pipeline=self.pipeline,
                new_status=PipelineStatus.DONE.value
            )
            self.repo.upsert_source(
                pipeline=self.pipeline,
                summary=self.pipeline.summary()
            )
            return stored
        finally:
            # Always detach monitoring handler even if any step fails
            self._run_clean_orchestration()