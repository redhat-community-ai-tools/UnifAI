from typing import Any, Dict, Iterator, Optional, Union
from session.user_session_manager import UserSessionManager
from session.repository.repository import SessionRepository
from session.workflow_session import WorkflowSession
from graph.state.graph_state import GraphState
from core.context import set_current_context
from core.channels import SessionChannel
from engine.channels import LangGraphEmitter
from session.channels import LocalSessionChannel
from .status import SessionStatus
from .utils import derive_title

SessionOrId = Union[WorkflowSession, str]


class SessionExecutor:
    """
    SRP: only handles "run" and "stream" of a WorkflowSession.
    Can accept either a WorkflowSession or a run_id string.
    """

    def __init__(
            self,
            session_manager: UserSessionManager,
            repository: SessionRepository
    ):
        self._sessions = session_manager
        self._repo = repository

    def _pre_run(
            self,
            session: WorkflowSession,
            inputs: Dict[str, Any],
            scope: str,
            logged_in_user: str,
            streaming: bool = False
    ) -> Optional[SessionChannel]:
        """
        1) add title to session metadata
        2) bind RunContext into ContextVar
        3) seed input into the GraphState
        4) if streaming, create channel and prepare nodes
        5) update status
        6) persist
        
        Returns:
            SessionChannel if streaming=True, None otherwise
        """
        if session.metadata.title is None:
            if title := derive_title(inputs):
                session.metadata.title = title
        ctx = session.run_context.change_scope(scope)  # TODO remove scope parameter from context
        ctx = ctx.set_logged_in_user(logged_in_user)  # TODO remove logged_in_user parameter from context
        set_current_context(ctx)
        session.graph_state.update(inputs)
        
        # Streaming setup - create channel and prepare nodes
        channel = None
        if streaming:
            channel = self._create_streaming_channel(session)
            session.prepare_for_streaming(channel)
        
        session.update_status(SessionStatus.RUNNING)
        self._repo.save(session)
        
        return channel

    def _post_run(
            self,
            session: WorkflowSession,
            final_state,
            streaming: bool = False,
            channel: Optional[SessionChannel] = None
    ) -> None:
        """
        1) attach final state
        2) if streaming, cleanup channel from nodes and close channel
        3) mark context finished
        4) update status
        5) persist
        """
        session.graph_state = GraphState(**final_state)
        
        # Streaming cleanup
        if streaming:
            session.cleanup_streaming()
            if channel:
                channel.close()
        
        session.run_context = session.run_context.mark_finished()
        set_current_context(session.run_context)
        session.update_status(SessionStatus.COMPLETED)
        self._repo.save(session)

    def _error_run(
            self,
            session: WorkflowSession,
            error: Exception,
            streaming: bool = False,
            channel: Optional[SessionChannel] = None
    ) -> None:
        """
        1) if streaming, cleanup channel from nodes and close channel
        2) mark context finished
        3) update status
        4) persist
        """
        if streaming:
            session.cleanup_streaming()
            if channel:
                channel.close()
        
        session.run_context = session.run_context.mark_finished()
        session.update_status(SessionStatus.FAILED)
        self._repo.save(session)

    def run(
            self,
            session: WorkflowSession,
            inputs: Dict[str, Any],
            scope: str = "public",
            logged_in_user=""
    ) -> GraphState:
        """
        Run the graph to completion and return the final GraphState.
        """
        self._pre_run(session, inputs, scope, logged_in_user, streaming=False)
        try:
            final_state = session.executable_graph.run(session.graph_state)
        except Exception as e:
            self._error_run(session, e, streaming=False)
            raise e

        self._post_run(session, final_state, streaming=False)
        return final_state

    def stream(
            self,
            session: WorkflowSession,
            inputs: Dict[str, Any],
            scope: str = "public",
            logged_in_user: str = "",
            **stream_kwargs: Any
    ) -> Iterator[Any]:
        """
        Stream execution chunks, then persist at the end.
        """
        channel = self._pre_run(session, inputs, scope, logged_in_user, streaming=True)

        try:
            for chunk in session.executable_graph.stream(
                    session.graph_state,
                    **stream_kwargs
            ):
                yield chunk
                try:
                    # will work only if custom is enabled in stream_kwargs
                    session.graph_state = chunk[1].get("state") if isinstance(chunk, (list, tuple)) and isinstance(
                        chunk[1], dict) else None
                except Exception as e:
                    raise e
            
            # Generator completed normally - finalize
            self._post_run(session, session.graph_state, streaming=True, channel=channel)

        except GeneratorExit:
            # Consumer stopped iterating early - still need to cleanup
            self._post_run(session, session.graph_state, streaming=True, channel=channel)
            raise
        except Exception as e:
            self._error_run(session, e, streaming=True, channel=channel)
            raise e

    def _create_streaming_channel(self, session: WorkflowSession) -> SessionChannel:
        """
        Factory method for creating the streaming channel.
        Override or extend for different channel types (e.g., Redis).
        """
        emitter = LangGraphEmitter()
        return LocalSessionChannel(
            session_id=session.get_run_id(),
            emitter=emitter
        )
