"""
A2AProvider - High-level interface for A2A communication.

Works with ChatMessage (your system type).
Orchestrates client, converter, and polling.
"""

import asyncio
from typing import Optional, Dict, Any, AsyncIterator, Iterator, Tuple

from pydantic import HttpUrl

from a2a.types import AgentCard, TaskState

from global_utils.utils.async_bridge import get_async_bridge

from elements.llms.common.chat.message import ChatMessage
from elements.providers.a2a_client.client import A2AClient, A2AClientError, A2AConnectionError
from elements.providers.a2a_client.converter import A2AConverter, ConversionResult
from elements.providers.a2a_client.result import A2AResult


class A2ATaskError(A2AClientError):
    """Task execution error."""

    def __init__(
            self,
            message: str,
            task_id: Optional[str] = None,
            state: Optional[TaskState] = None,
    ):
        super().__init__(message)
        self.task_id = task_id
        self.state = state


class A2ATimeoutError(A2AClientError):
    """Polling timeout."""
    pass


class A2AProvider:
    """
    High-level A2A interface.
    
    Provides ChatMessage-based API over A2A protocol.
    
    Flow:
        ChatMessage → A2A Message → Agent → A2AResult → ChatMessage
    """

    def __init__(
            self,
            base_url: HttpUrl,
            agent_card: Optional[AgentCard] = None,
            headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize provider.
        
        Args:
            base_url: A2A agent URL
            agent_card: Pre-fetched agent card (optional)
            headers: HTTP headers for auth (optional)
        """
        self.base_url = base_url
        self.agent_card = agent_card
        self.headers = headers or {}
        self._converter = A2AConverter()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Initialize on first use."""
        if self._initialized:
            return

        async with A2AClient(
                self.base_url,
                agent_card=self.agent_card,
                headers=self.headers,
        ) as client:
            self.agent_card = client.agent_card

        self._initialized = True

    async def send_message(
            self,
            message: ChatMessage,
            task_id: Optional[str] = None,
            context_id: Optional[str] = None,
            part_metadata: Optional[Dict[str, Any]] = None,
            wait_for_completion: bool = True,
            raise_on_error: bool = False,
            poll_interval: float = 0.5,
            max_poll_attempts: int = 60,
    ) -> Tuple[ChatMessage, Dict[str, Any]]:
        """
        Send message and get response.
        
        Args:
            message: ChatMessage to send
            task_id: Optional task ID for multi-turn
            context_id: Optional context ID for multi-turn
            part_metadata: Metadata for message parts.
                          Default: {"type": "user_message"}
                          Pass {} for no metadata.
            wait_for_completion: Wait for task to complete
            raise_on_error: Raise exception on failure (default: return error in message)
            poll_interval: Seconds between polls
            max_poll_attempts: Maximum polling attempts
            
        Returns:
            Tuple of (response ChatMessage, metadata dict)
        """
        await self._ensure_initialized()

        async with A2AClient(
                self.base_url,
                agent_card=self.agent_card,
                headers=self.headers,
        ) as client:
            a2a_message = self._converter.to_a2a_message(
                message,
                task_id=task_id,
                context_id=context_id,
                part_metadata=part_metadata,
            )

            result = await client.send(a2a_message)

            if raise_on_error and result.is_failure:
                raise A2ATaskError(
                    result.error_message or "Task failed",
                    task_id=result.task_id,
                    state=result.state,
                )

            if wait_for_completion and not result.is_complete and not result.is_failure:
                result = await self._poll(
                    client,
                    result.task_id,
                    poll_interval,
                    max_poll_attempts,
                    raise_on_error,
                )

            conversion = self._converter.to_chat_message(result)
            return conversion.message, conversion.metadata

    async def _poll(
            self,
            client: A2AClient,
            task_id: str,
            interval: float,
            max_attempts: int,
            raise_on_error: bool,
    ) -> A2AResult:
        """Poll until completion or timeout."""
        for _ in range(max_attempts):
            await asyncio.sleep(interval)

            result = await client.get_task(task_id)

            if raise_on_error and result.is_failure:
                raise A2ATaskError(
                    result.error_message or "Task failed",
                    task_id=task_id,
                    state=result.state,
                )

            if result.is_complete:
                return result

            if result.requires_input:
                if raise_on_error:
                    raise A2ATaskError("Input required", task_id=task_id, state=result.state)
                return result

            if result.requires_auth:
                if raise_on_error:
                    raise A2ATaskError("Authentication required", task_id=task_id, state=result.state)
                return result

        raise A2ATimeoutError(f"Polling timeout after {max_attempts * interval}s")

    async def stream_message(
            self,
            message: ChatMessage,
            task_id: Optional[str] = None,
            context_id: Optional[str] = None,
            part_metadata: Optional[Dict[str, Any]] = None,
            raise_on_error: bool = False,
    ) -> AsyncIterator[ChatMessage]:
        """
        Stream message and yield responses.
        
        Args:
            message: ChatMessage to send
            task_id: Optional task ID
            context_id: Optional context ID
            part_metadata: Metadata for message parts.
                          Default: {"type": "user_message"}
                          Pass {} for no metadata.
            raise_on_error: Raise on error (default: yield error in message)
            
        Yields:
            ChatMessage for each streaming update with content
        """
        await self._ensure_initialized()

        async with A2AClient(
                self.base_url,
                agent_card=self.agent_card,
                headers=self.headers,
        ) as client:
            a2a_message = self._converter.to_a2a_message(
                message,
                task_id=task_id,
                context_id=context_id,
                part_metadata=part_metadata,
            )

            async for result in client.stream(a2a_message):
                if result.is_failure:
                    if raise_on_error:
                        raise A2ATaskError(
                            result.error_message or "Stream error",
                            task_id=result.task_id,
                            state=result.state,
                        )

                conversion = self._converter.to_chat_message(result)
                if conversion.message.content:
                    yield conversion.message

    def send_message_sync(
            self,
            message: ChatMessage,
            **kwargs,
    ) -> Tuple[ChatMessage, Dict[str, Any]]:
        """Sync version of send_message."""
        with get_async_bridge() as bridge:
            return bridge.run(self.send_message(message, **kwargs))

    def stream_message_sync(
            self,
            message: ChatMessage,
            **kwargs,
    ) -> Iterator[ChatMessage]:
        """Sync version of stream_message."""
        with get_async_bridge() as bridge:
            for chunk in bridge.iterate(self.stream_message(message, **kwargs)):
                yield chunk

    async def cancel_task(self, task_id: str) -> Tuple[ChatMessage, Dict[str, Any]]:
        """
        Cancel a running task.
        
        Args:
            task_id: ID of task to cancel
            
        Returns:
            Tuple of (ChatMessage with status, metadata)
        """
        async with A2AClient(
                self.base_url,
                agent_card=self.agent_card,
                headers=self.headers,
        ) as client:
            result = await client.cancel_task(task_id)
            conversion = self._converter.to_chat_message(result)
            return conversion.message, conversion.metadata

    def cancel_task_sync(self, task_id: str) -> Tuple[ChatMessage, Dict[str, Any]]:
        """Sync version of cancel_task."""
        with get_async_bridge() as bridge:
            return bridge.run(self.cancel_task(task_id))

    @property
    def skills(self) -> list:
        """Get available skill names."""
        if not self.agent_card or not self.agent_card.skills:
            return []
        return [s.name for s in self.agent_card.skills if s.name]

    @classmethod
    async def create(cls, base_url: HttpUrl, **kwargs) -> "A2AProvider":
        """Create and initialize provider."""
        provider = cls(base_url, **kwargs)
        await provider._ensure_initialized()
        return provider

    @classmethod
    def create_sync(cls, base_url: HttpUrl, **kwargs) -> "A2AProvider":
        """Create and initialize provider (sync)."""
        with get_async_bridge() as bridge:
            return bridge.run(cls.create(base_url, **kwargs))

    def __repr__(self) -> str:
        agent_name = self.agent_card.name if self.agent_card else "unknown"
        return f"A2AProvider(agent='{agent_name}', url='{self.base_url}')"
