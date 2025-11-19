import hashlib
from typing import Final, Any


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
