"""
Symmetric field encryption using Fernet.

Provides a reusable cipher for encrypting/decrypting individual string
fields (tokens, secrets) at rest or in transit.  Used by the credential
store (at-rest) and by auth actions (in-transit to browser).
"""

from typing import Optional

FERNET_PREFIX = "gAAAAAB"


class FieldCipher:
    """Fernet wrapper for encrypting/decrypting individual string fields.

    The decrypt method is prefix-aware: values that don't start with the
    Fernet prefix are returned unchanged, making it safe to call on both
    encrypted and plaintext values (e.g. user-typed API keys).
    """

    def __init__(self, key: str):
        from cryptography.fernet import Fernet
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return value
        if not value.startswith(FERNET_PREFIX):
            return value
        return self._fernet.decrypt(value.encode()).decode()
