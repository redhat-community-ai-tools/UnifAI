import functools
from typing import Callable
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
                raise
        return wrapper
    return decorator


class PipelineDuplicatedDocBreak(Exception):
    """Signal to halt the pipeline gracefully (not an error)."""
    pass


def break_if_skipped(fn: Callable) -> Callable:
    """
    Decorator for the collect step. After running the wrapped function, it checks
    the current pipeline status in the repository. If the pipeline was marked as
    SKIPPED (e.g., due to duplicate detection) or the document was deleted (status None),
    it raises PipelineBreak to stop execution cleanly before subsequent steps.
    """
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        result = fn(self, *args, **kwargs)
        current_status = self.repo.get_pipeline_field(self.pipeline.get_pipeline_id(), "status", None)
        if current_status == PipelineStatus.SKIPPED.value or current_status is None:
            raise PipelineDuplicatedDocBreak()
        return result
    return wrapper
