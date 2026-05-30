"""
MongoDB implementation of the TokenRepository port.

Stores hashed tokens with metadata. The plaintext token is never persisted —
only a SHA-256 hash is stored for validation.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from pymongo import ASCENDING
from pymongo.database import Database

from tokens.models import TOKEN_PREFIX, ApiToken, TokenCreateResult, TokenUserData
from tokens.repository.repository import TokenRepository

_TOKEN_BYTE_LENGTH = 32


def _generate_token() -> str:
    return f"{TOKEN_PREFIX}{secrets.token_hex(_TOKEN_BYTE_LENGTH)}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MongoTokenRepository(TokenRepository):

    def __init__(self, db: Database, coll_name: str = "api_tokens"):
        self._coll = db[coll_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self._coll.create_index("token_hash", unique=True, name="uq_token_hash")
        self._coll.create_index(
            [("user_id", ASCENDING), ("revoked", ASCENDING)],
            name="idx_user_active",
        )
        self._coll.create_index("expires_at", expireAfterSeconds=0, name="ttl_expires")

    def create(self, user_id: str, name: str, user_data: TokenUserData,
               ttl_seconds: int = 36000) -> TokenCreateResult:
        token = _generate_token()
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc)

        doc = {
            "token_hash": _hash_token(token),
            "user_id": user_id,
            "name": name,
            "user_data": user_data.model_dump(),
            "created_at": now,
            "expires_at": expires_at,
            "last_used_at": None,
            "revoked": False,
        }
        self._coll.insert_one(doc)

        return TokenCreateResult(
            token=token,
            name=name,
            expires_at=expires_at.isoformat(),
            expires_in=ttl_seconds,
        )

    def validate(self, token: str) -> Optional[TokenUserData]:
        token_hash = _hash_token(token)
        doc = self._coll.find_one({
            "token_hash": token_hash,
            "revoked": False,
        })

        if not doc:
            return None

        if doc.get("expires_at") and doc["expires_at"] < datetime.now(timezone.utc):
            return None

        self._coll.update_one(
            {"token_hash": token_hash},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
        return TokenUserData(**(doc.get("user_data") or {"username": doc["user_id"]}))

    def list_by_user(self, user_id: str) -> List[ApiToken]:
        cursor = self._coll.find(
            {"user_id": user_id, "revoked": False},
            {"_id": 0},
        ).sort("created_at", -1)

        return [ApiToken(**doc) for doc in cursor]

    def revoke(self, user_id: str, name: str) -> bool:
        result = self._coll.update_one(
            {"user_id": user_id, "name": name, "revoked": False},
            {"$set": {"revoked": True}},
        )
        return result.modified_count > 0

    def revoke_all(self, user_id: str) -> int:
        result = self._coll.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {"revoked": True}},
        )
        return result.modified_count
