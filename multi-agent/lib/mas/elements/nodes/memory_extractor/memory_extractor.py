import logging
from typing import Any, ClassVar, Dict, Iterable, Optional

from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.elements.nodes.common.base_node import BaseNode
from mas.elements.nodes.common.context_binder import bind_tool_context
from mas.elements.tools.memory.extraction import MemoryExtractor, persist
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView

logger = logging.getLogger(__name__)


def _as_message(item: Any) -> Optional[ChatMessage]:
    if isinstance(item, ChatMessage):
        return item
    if isinstance(item, dict):
        try:
            return ChatMessage(role=Role(item.get("role")), content=str(item.get("content") or ""))
        except Exception:
            return None
    return None


class MemoryExtractorNode(BaseNode):
    """Runs a memory extraction over the session transcript and persists it.

    Never raises on bad model output or on a refused write: the outcome is a short summary
    written to the node's output channel entry (counts and errors).
    """

    READS: ClassVar[set[str]] = {Channel.MESSAGES}
    WRITES: ClassVar[set[str]] = {Channel.NODES_OUTPUT}

    def __init__(
        self,
        *,
        llm: Any,
        memory: Any,
        classification: Optional[str] = None,
        local_llm: Any = None,
        restricted_classifications: Iterable[str] = (),
        execution_holder: Any = None,
        **kwargs: Any,
    ):
        super().__init__(**kwargs)
        self._llm = llm
        self._memory = memory
        self._classification = (classification or "").strip() or None
        self._local_llm = local_llm
        self._restricted = {c.strip().lower() for c in restricted_classifications if c and c.strip()}
        self._execution_holder = execution_holder
        self._extractor = MemoryExtractor(llm, llm_for_classification=self._llm_for_classification)

    def _llm_for_classification(self, classification: str) -> Any:
        """Restricted classes go to the local LLM only (None refuses); others use the default LLM."""
        if classification.strip().lower() in self._restricted:
            return self._local_llm
        return self._llm

    def _session_id(self) -> str:
        try:
            return self._execution_holder.context.session_id or ""
        except Exception:
            return ""

    def run(self, state: StateView) -> StateView:
        summary = self.extract_and_persist(list(state.get(Channel.MESSAGES, []) or []))
        logger.info("memory_extractor.done", extra={"summary": summary})
        outputs = dict(state.get(Channel.NODES_OUTPUT, {}) or {})
        outputs[self._output_key()] = summary
        state[Channel.NODES_OUTPUT] = outputs
        return state

    def _output_key(self) -> str:
        try:
            return self.uid
        except Exception:
            return "memory_extractor"

    def extract_and_persist(self, raw_messages: list) -> str:
        """Return a one-line summary; every failure is reported in it, none is raised."""
        try:
            transcript = [m for m in (_as_message(i) for i in raw_messages) if m is not None]
            result = self._extractor.extract(transcript, classification=self._classification)
            if not result.ok:
                return f"memory extraction failed: {result.error}"
            bind_tool_context([self._memory], session_id=self._session_id(), agent_id=self._output_key())
            report = persist(result, self._memory)
            text = (
                f"memory extraction {'ok' if report.ok else 'incomplete'}: "
                f"{report.facts_written} facts, {report.memories_written} memories written, "
                f"{result.dropped} dropped"
            )
            if report.errors:
                text += f"; {len(report.errors)} errors: " + "; ".join(report.errors[:3])
            return text
        except Exception as exc:  # never break the workflow on a memory side task
            logger.warning("memory_extractor.failed", exc_info=True)
            return f"memory extraction failed: {type(exc).__name__}"
