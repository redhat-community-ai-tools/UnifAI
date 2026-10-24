"""Local file system storage adapter for document uploads."""
import base64
import hashlib
import os
from typing import List, Dict

from global_utils.utils.file_utils import secure_filename
import logging

logger = logging.getLogger(__name__)



def user_upload_dir(base: str, owner: str) -> str:
    """Upload folder of one user: two users uploading the same file name never touch each other's file."""
    return os.path.join(base, hashlib.sha256(owner.encode()).hexdigest()[:24])

class LocalFileStorage:
    """
    Local filesystem storage for uploaded documents.
    
    Handles saving base64-encoded files to a configured upload directory.
    Uses secure_filename to sanitize filenames before saving.
    
    Usage:
        storage = LocalFileStorage("/path/to/uploads")
        storage.save_files([
            {"name": "doc.pdf", "content": "base64_encoded_content..."}
        ])
    """

    def __init__(self, upload_folder: str):
        """
        Initialize local file storage.
        
        Args:
            upload_folder: Directory path for storing uploaded files
        """
        self._upload_folder = upload_folder
        os.makedirs(upload_folder, exist_ok=True)

    @property
    def upload_folder(self) -> str:
        """Get the upload folder path."""
        return self._upload_folder

    def save_files(self, files: List[Dict[str, str]], owner: str = "") -> List[str]:
        """
        Save multiple base64-encoded files.
        
        Args:
            files: List of file dicts with "name" and "content" (base64) keys
            
        Returns:
            List of saved file paths
            
        Raises:
            ValueError: If file dict is missing required keys
            Exception: If file write fails
        """
        saved_paths = []
        
        for file in files:
            if "name" not in file or "content" not in file:
                raise ValueError("File must have 'name' and 'content' keys")
            self._reject_unsafe_name(file["name"])
            
            path = self.save_base64(file["name"], file["content"], owner)
            saved_paths.append(path)
        
        return saved_paths

    @staticmethod
    def _reject_unsafe_name(name: object) -> None:
        """Reject names that are not a plain file name (separators, dot segments, NUL)."""
        if (
            not isinstance(name, str)
            or not name.strip()
            or "\x00" in name
            or "/" in name
            or "\\" in name
            or name.strip() in (".", "..")
        ):
            raise ValueError("Invalid file name")

    def save_base64(self, filename: str, base64_content: str, owner: str = "") -> str:
        """
        Save a single base64-encoded file.
        
        Args:
            filename: Original filename (will be sanitized)
            base64_content: Base64-encoded file content
            
        Returns:
            Full path where the file was saved
        """
        content = base64.b64decode(base64_content)
        return self.save(filename, content, owner)

    def save(self, filename: str, content: bytes, owner: str = "") -> str:
        """
        Save raw bytes to a file.
        
        Args:
            filename: Original filename (will be sanitized)
            content: Raw file bytes
            
        Returns:
            Full path where the file was saved
        """
        safe_name = secure_filename(filename)
        folder = user_upload_dir(self._upload_folder, owner) if owner else self._upload_folder
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, safe_name)
        root = os.path.realpath(self._upload_folder)
        if os.path.commonpath([root, os.path.realpath(path)]) != root:
            raise ValueError("Invalid file name")

        with open(path, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved file: {safe_name}")
        return path

    def get_path(self, filename: str) -> str:
        """
        Get the full path for a filename (without saving).
        
        Args:
            filename: Original filename (will be sanitized)
            
        Returns:
            Full path where the file would be stored
        """
        safe_name = secure_filename(filename)
        return os.path.join(self._upload_folder, safe_name)

    def exists(self, filename: str) -> bool:
        """
        Check if a file exists in storage.
        
        Args:
            filename: Original filename (will be sanitized)
            
        Returns:
            True if file exists
        """
        return os.path.exists(self.get_path(filename))

    def delete(self, filename: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            filename: Original filename (will be sanitized)
            
        Returns:
            True if file was deleted, False if it didn't exist
        """
        path = self.get_path(filename)
        
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted file: {secure_filename(filename)}")
            return True
        return False

