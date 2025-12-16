from abc import ABC, abstractmethod
from graph.models import StepContext
from graph.state.graph_state import GraphState, Channel
from graph.state.state_view import StateView
from typing import Optional, Any, Mapping, ClassVar
from elements.llms.common.chat.message import ChatMessage, Role
from core.contracts import SupportsStateContext
from elements.nodes.common.capabilities.streaming_capable import StreamingCapableMixin


class BaseNode(StreamingCapableMixin, SupportsStateContext, ABC):
    """
    Base node for all graph elements.
    
    Streaming is provided via StreamingCapableMixin.
    Channel is injected via set_streaming_channel() before execution.
    
    MRO: StreamingCapableMixin → SupportsStateContext → ABC → object
    Subclasses should list their mixins BEFORE BaseNode:
        class MyNode(SomeMixin, OtherMixin, BaseNode): ...
    """

    # Base channels that ALL nodes must have
    BASE_READS: ClassVar[set[str]] = set()
    BASE_WRITES: ClassVar[set[str]] = set()

    # Node-specific channels (to be overridden by subclasses)
    READS: ClassVar[set[str]] = set()
    WRITES: ClassVar[set[str]] = set()

    def __init__(self, *, retries: int = 1, **kwargs: Any):
        super().__init__(**kwargs)  # MRO
        self.retries = retries
        self._ctx: Optional[StepContext] = None

    @abstractmethod
    def run(self, state: StateView) -> StateView:
        ...

    def __call__(self,
                 state: GraphState,
                 config) -> GraphState:
        # Create StateView with all channels (base + mixin + node-specific)
        all_reads = self.total_reads()
        all_writes = self.total_writes()
        wrapped_state = StateView(state, reads=all_reads, writes=all_writes)

        # Store state for helper methods
        self._state = wrapped_state

        # Run node logic
        self.run(wrapped_state)
        result = wrapped_state.backing_state

        # Stream completion
        streamable_state = result.get_streamable_state()
        self._stream({
            "type": "complete",
            "state": result
        })

        return result

    def _base_stream_data(self) -> dict[str, Any]:
        """Core metadata every chunk must carry. Used by StreamingCapableMixin."""
        return {
            "node": self.uid,
            "display_name": self.display_name,
        }

    def _stream_field(self, field_name: str, value: Any = None) -> None:
        """
        Stream a specific state field during execution.
        Useful for streaming field updates mid-execution.
        
        Args:
            field_name: Name of the field to stream
            value: Value to stream (if None, fetches from current state)
        """
        if value is None and hasattr(self, '_state'):
            value = self._state.backing_state.get(field_name)
        
        self._stream({
            "type": "field_update",
            "field": field_name,
            "value": value
        })

    def set_context(self, step_ctx: StepContext) -> None:
        """
        Set the step context for this node.
        """
        self._ctx = step_ctx

    def get_state(self) -> StateView:
        """
        Get the current state view for this node.
        
        Returns the state view that provides access to graph channels
        with proper read/write permissions.
        """
        if not hasattr(self, '_state') or self._state is None:
            raise RuntimeError("State not available - called outside of execution")
        return self._state
    
    def get_context(self) -> StepContext:
        """
        Get the current step context for this node.
        
        Returns the step context that provides access to node metadata,
        adjacent nodes, and other execution context information.
        """
        if self._ctx is None:
            raise RuntimeError("Context not available - called outside of execution")
        return self._ctx
    
    def get_adjacent_nodes(self):
        """
        Get adjacent nodes from context.
        
        Returns:
            AdjacentNodes model with rich API for working with adjacent nodes
        """
        from graph.models import AdjacentNodes
        context = self.get_context()
        adjacent_nodes = getattr(context, 'adjacent_nodes', None)
        if adjacent_nodes is None:
            return AdjacentNodes.empty()
        return adjacent_nodes



    # ===== Clean Communication Helpers =====

    def promote_to_messages(self, content) -> None:
        """
        Promote content to PUBLIC conversation channel.
        
        Clean separation: This is for content that should be visible
        to end users and become part of the final conversation.
        """

        if not hasattr(self, '_state'):
            raise RuntimeError("promote_to_messages called outside of run()")

        msgs = list(self._state.get(Channel.MESSAGES, []))

        if isinstance(content, str):
            msgs.append(ChatMessage(role=Role.ASSISTANT, content=content))
        elif hasattr(content, 'role') and hasattr(content, 'content'):  # ChatMessage-like
            msgs.append(content)
        else:
            msgs.append(ChatMessage(role=Role.ASSISTANT, content=str(content)))

        self._state[Channel.MESSAGES] = msgs

    @property
    def uid(self) -> str:
        return self.get_context().uid

    @property
    def display_name(self) -> str:
        return self.get_context().metadata.display_name

    @classmethod
    def total_reads(cls) -> set[str]:
        """
        Collect all read channels from the entire inheritance hierarchy.
        
        Combines:
        - BASE_READS from BaseNode
        - MIXIN_READS from any mixins in the MRO
        - READS from the concrete node class
        """
        all_reads = set()

        # Walk the MRO (Method Resolution Order) to collect channels
        for klass in cls.__mro__:
            # Add BASE_READS (from BaseNode)
            if hasattr(klass, 'BASE_READS'):
                all_reads.update(klass.BASE_READS)

            # Add MIXIN_READS (from mixins like LlmCapableMixin)
            if hasattr(klass, 'MIXIN_READS'):
                all_reads.update(klass.MIXIN_READS)

            # Add READS (from the specific class)
            if hasattr(klass, 'READS') and klass.READS:
                all_reads.update(klass.READS)

        return all_reads

    @classmethod
    def total_writes(cls) -> set[str]:
        """
        Collect all write channels from the entire inheritance hierarchy.
        
        Combines:
        - BASE_WRITES from BaseNode
        - MIXIN_WRITES from any mixins in the MRO
        - WRITES from the concrete node class
        """
        all_writes = set()

        # Walk the MRO (Method Resolution Order) to collect channels
        for klass in cls.__mro__:
            # Add BASE_WRITES (from BaseNode)
            if hasattr(klass, 'BASE_WRITES'):
                all_writes.update(klass.BASE_WRITES)

            # Add MIXIN_WRITES (from mixins like LlmCapableMixin)
            if hasattr(klass, 'MIXIN_WRITES'):
                all_writes.update(klass.MIXIN_WRITES)

            # Add WRITES (from the specific class)
            if hasattr(klass, 'WRITES') and klass.WRITES:
                all_writes.update(klass.WRITES)

        return all_writes
