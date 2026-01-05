"""
File utility functions for file operations across the application.
"""
import os
import re
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Final, Optional

logger = logging.getLogger(__name__)

_DEFAULT_CHUNK_SIZE: Final[int] = 1024 * 1024  # 1MB


def compute_file_md5(file_path: str, chunk_size: int = _DEFAULT_CHUNK_SIZE) -> str:
    """
    Compute the MD5 checksum of a file by streaming in chunks.

    Args:
        file_path: Absolute path to the file on disk
        chunk_size: Read size per iteration (bytes)

    Returns:
        Hexadecimal MD5 digest string
    """
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as file_handle:
        while True:
            chunk = file_handle.read(chunk_size)
            if not chunk:
                break
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def cleanup_file(file_path: Optional[str], context: str = "") -> bool:
    """
    Safely remove a file from disk using pathlib for robust path handling.

    Args:
        file_path: Path to the file to remove
        context: Optional context for logging (e.g., "after validation failure")

    Returns:
        True if file was removed, False otherwise
    """
    if not file_path:
        return False
    
    path = Path(file_path)
    
    if not path.exists():
        return False
    
    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        
        context_msg = f" {context}" if context else ""
        logger.info(f"Cleaned up file{context_msg}: {file_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to clean up file {file_path}: {e}")
        return False


def secure_filename(filename: str) -> str:
    """
    Return a secure version of a filename.
    
    This is a pure Python implementation that doesn't depend on werkzeug.
    It normalizes the filename by:
    - Converting spaces to underscores
    - Removing path separators to prevent directory traversal
    - Keeping only safe characters (alphanumeric, underscores, hyphens, dots)
    - Preserving file extension
    
    Args:
        filename: The original filename
        
    Returns:
        A sanitized filename safe for filesystem storage
    """
    # Normalize unicode
    # Remove any path components (prevent directory traversal)
    filename = os.path.basename(filename)
    
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    
    # Keep only safe characters: alphanumeric, underscore, hyphen, dot
    # Use regex to filter out unsafe characters
    filename = re.sub(r'[^\w\-.]', '', filename)
    
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = 'unnamed_file'
    
    return filename

