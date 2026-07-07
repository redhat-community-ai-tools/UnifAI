"""
File upload port, DTOs, and exception.

Defines the contract between the session use-case and file upload
infrastructure adapters (e.g. Gemini File API).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


class FileUploadError(Exception):
    """Raised when file upload fails after exhausting retries.

    Adapters MUST wrap vendor-specific exceptions into this type.
    The message should be user-presentable.
    """

    def __init__(self, message: str, failed_file: str = "", retriable: bool = False):
        self.failed_file = failed_file
        self.retriable = retriable
        super().__init__(message)


@dataclass(frozen=True)
class FileUploadRequest:
    """Single file to upload — input DTO for the port."""
    file_name: str
    file_bytes: bytes
    mime_type: str


@dataclass(frozen=True)
class FileUploadResult:
    """Successful upload reference — output DTO from the port."""
    file_name: str
    mime_type: str
    file_uri: str
    size_bytes: int


@dataclass(frozen=True)
class FileUploadLimits:
    """Authoritative upload constraints — shared between adapter validation and UI hints.

    Must be constructed explicitly from config to avoid default drift.
    """
    max_files: int
    max_file_size_bytes: int
    min_file_size_bytes: int
    allowed_mime_types: tuple[str, ...]


class IFileUploadService(ABC):
    """Outbound port for file upload operations."""

    @abstractmethod
    def upload_batch(self, files: List[FileUploadRequest]) -> List[FileUploadResult]:
        """Upload multiple files atomically.

        Returns results in the same order as the input list.
        If any upload fails, the adapter cleans up already-uploaded
        files and raises FileUploadError.
        """
        ...
