"""
A2AConverter - Bidirectional conversion between A2A SDK types and ChatMessage.

Handles content extraction from all Part types (Text, File, Data).
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4
from enum import Enum

from pydantic import BaseModel

from a2a.types import (
    Message,
    Part,
    TextPart,
    FilePart,
    DataPart,
    FileWithBytes,
    FileWithUri,
    Artifact,
    Role as A2ARole,
)
from a2a.utils import get_text_parts

from elements.llms.common.chat.message import ChatMessage, Role
from elements.providers.a2a_client.result import A2AResult, ResultKind


class FileInfo(BaseModel):
    """File information extracted from FilePart."""

    name: Optional[str] = None
    mime_type: Optional[str] = None
    is_inline: bool = False
    content: str = ""

    model_config = {"frozen": True}


class ConversionResult(BaseModel):
    """Result of converting A2AResult to ChatMessage."""

    message: ChatMessage
    metadata: Dict[str, Any]
    files: Tuple[FileInfo, ...] = ()
    data: Tuple[Dict[str, Any], ...] = ()

    model_config = {"arbitrary_types_allowed": True}


class A2AConverter:
    """
    Bidirectional converter between A2A SDK types and ChatMessage.
    
    Outbound: ChatMessage → A2A Message
    Inbound: A2AResult → ChatMessage
    """

    ROLE_MAP = {
        Role.USER: A2ARole.user,
        Role.ASSISTANT: A2ARole.agent,
        Role.SYSTEM: A2ARole.user,
        Role.TOOL: A2ARole.user,
    }

    # Default metadata for outbound messages
    DEFAULT_PART_METADATA = {"type": "user_message"}

    def to_a2a_message(
            self,
            message: ChatMessage,
            task_id: Optional[str] = None,
            context_id: Optional[str] = None,
            part_metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """
        Convert ChatMessage to A2A Message.
        
        Args:
            message: ChatMessage to convert
            task_id: Optional task ID for multi-turn
            context_id: Optional context ID for multi-turn
            part_metadata: Metadata for the text part. 
                          Default: {"type": "user_message"}
                          Pass {} for no metadata.
        """
        role = self.ROLE_MAP.get(message.role, A2ARole.user)

        # Use default metadata if not specified
        metadata = part_metadata if part_metadata is not None else self.DEFAULT_PART_METADATA

        text_part = TextPart(
            text=message.content,
            metadata=metadata if metadata else None,
        )

        return Message(
            role=role,
            parts=[Part(root=text_part)],
            message_id=uuid4().hex,
            task_id=task_id,
            context_id=context_id,
        )

    def to_chat_message(self, result: A2AResult) -> ConversionResult:
        """
        Convert A2AResult to ChatMessage with full metadata.
        
        Errors are included in content so caller sees them in chat.
        """
        text, files, data = self._extract_content(result)

        if result.is_error or result.is_failure:
            error_text = self._format_error(result)
            text = f"{error_text}\n\n{text}" if text else error_text

        if not text:
            text = self._fallback_text(result)

        message = ChatMessage(role=Role.ASSISTANT, content=text)
        metadata = self._build_metadata(result, files, data)

        return ConversionResult(
            message=message,
            metadata=metadata,
            files=tuple(files),
            data=tuple(data),
        )

    def to_chat_message_simple(self, result: A2AResult) -> ChatMessage:
        """Convert A2AResult to ChatMessage only (no metadata)."""
        return self.to_chat_message(result).message

    def _format_error(self, result: A2AResult) -> str:
        """Format error for display in chat."""
        error_msg = result.error_message or "An error occurred"
        if result.error_code:
            return f"Error ({result.error_code}): {error_msg}"
        return f"Error: {error_msg}"

    def _extract_content(self, result: A2AResult) -> Tuple[str, List[FileInfo], List[Dict]]:
        """Extract text, files, and data from result."""
        texts: List[str] = []
        files: List[FileInfo] = []
        data: List[Dict] = []

        if result.kind == ResultKind.TASK and result.task:
            for artifact in result.task.artifacts or []:
                t, f, d = self._from_parts(artifact.parts)
                if t:
                    texts.append(t)
                files.extend(f)
                data.extend(d)

            if not texts and result.task.status and result.task.status.message:
                t, f, d = self._from_parts(result.task.status.message.parts)
                if t:
                    texts.append(t)
                files.extend(f)
                data.extend(d)

        elif result.kind == ResultKind.MESSAGE and result.message:
            t, f, d = self._from_parts(result.message.parts)
            if t:
                texts.append(t)
            files.extend(f)
            data.extend(d)

        elif result.kind == ResultKind.ARTIFACT_EVENT and result.artifact_event:
            t, f, d = self._from_parts(result.artifact_event.artifact.parts)
            if t:
                texts.append(t)
            files.extend(f)
            data.extend(d)

        elif result.kind == ResultKind.STATUS_EVENT and result.status_message_obj:
            t, f, d = self._from_parts(result.status_message_obj.parts)
            if t:
                texts.append(t)
            files.extend(f)
            data.extend(d)

        return "\n".join(texts), files, data

    def _from_parts(self, parts: Optional[List[Part]]) -> Tuple[str, List[FileInfo], List[Dict]]:
        """Extract from list of Parts."""
        if not parts:
            return "", [], []

        texts: List[str] = []
        files: List[FileInfo] = []
        data: List[Dict] = []

        for part in parts:
            root = part.root if hasattr(part, "root") else part

            if isinstance(root, TextPart):
                texts.append(root.text)
            elif isinstance(root, FilePart):
                files.append(self._extract_file(root))
            elif isinstance(root, DataPart):
                data.append(root.data)

        return "\n".join(texts), files, data

    def _extract_file(self, file_part: FilePart) -> FileInfo:
        """Extract FileInfo from FilePart."""
        f = file_part.file
        if isinstance(f, FileWithBytes):
            return FileInfo(
                name=f.name,
                mime_type=f.mime_type,
                is_inline=True,
                content=f.bytes,
            )
        elif isinstance(f, FileWithUri):
            return FileInfo(
                name=f.name,
                mime_type=f.mime_type,
                is_inline=False,
                content=f.uri,
            )
        return FileInfo()

    def _fallback_text(self, result: A2AResult) -> str:
        """Fallback text for empty content."""
        if result.requires_input:
            return "Additional input is required to continue."
        if result.requires_auth:
            return "Authentication is required to continue."
        if result.is_canceled:
            return "Task was canceled."
        if result.state:
            return f"Task status: {result.state.value}"
        return ""

    def _build_metadata(
            self,
            result: A2AResult,
            files: List[FileInfo],
            data: List[Dict],
    ) -> Dict[str, Any]:
        """Build metadata dictionary."""
        return {
            "task_id": result.task_id,
            "context_id": result.context_id,
            "result_kind": result.kind.value,
            "state": result.state.value if result.state else None,
            "is_complete": result.is_complete,
            "is_terminal": result.is_terminal,
            "is_success": result.is_success,
            "is_error": result.is_error or result.is_failure,
            "is_failure": result.is_failure,
            "is_canceled": result.is_canceled,
            "is_streaming": result.is_streaming,
            "requires_input": result.requires_input,
            "requires_auth": result.requires_auth,
            "error_message": result.error_message,
            "error_code": result.error_code,
            "has_files": bool(files),
            "has_data": bool(data),
            "file_count": len(files),
            "data_count": len(data),
        }
