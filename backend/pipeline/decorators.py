import functools
from config.constants import PipelineStatus

def pipeline_step(status: str):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(self, *args, **kwargs):
            self.repo.update_pipeline_status(self.pipeline, status)

            try:
                return fn(self, *args, **kwargs)
            except Exception as e:
                self.pipeline.monitor.record_error(
                    pipeline_id=self.pipeline.get_pipeline_id(),
                    error_details=status,
                    error_message=str(e)
                )
                self.repo.update_pipeline_status(self.pipeline, PipelineStatus.FAILED.value)
                self.repo.upsert_source(
                    pipeline=self.pipeline,
                    summary={
                        "last_error": str(e),
                        "failed_at": status,
                    }
                )
                raise
        return wrapper
    return decorator
