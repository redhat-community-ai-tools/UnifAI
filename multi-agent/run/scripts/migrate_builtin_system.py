"""
Migration script: Transition from legacy builtin_status to the new ownership/visibility model.


Steps performed:
1. All existing resources with builtin_status != None get ownership="builtin" + visibility mapped.
2. All existing resources with builtin_status == None get ownership="custom".
3. Existing user_configs embedded on resources are migrated to the builtin_user_configs collection.
4. Legacy fields (builtin_status, configurable_keys, user_configs) are removed from all documents.

Note: Configurable field schemas are now derived at runtime from ReadOnlyHint annotations
on element Pydantic models — no separate builtin_schemas collection is needed.

Reverse migration (--reverse):
1. Embedded user_configs are restored on resources from the builtin_user_configs collection.
2. Resources with ownership="builtin" get builtin_status back ("public" if visibility=="public",
   else "draft"). Resources with ownership="custom" are left without a builtin_status field.
3. The ownership and visibility fields are removed from all documents.
4. The builtin_user_configs collection is dropped.

Note: This is a best-effort reversal. The original builtin_status value is not fully
recoverable for non-public resources (it collapses to "draft"), and configurable_keys
is not restored since it is now derived at runtime rather than stored.

Usage:
    python -m run.scripts.migrate_builtin_system [--dry-run] [--reverse] [--mongodb-ip localhost] [--mongodb-port 27017] [--encryption-key KEY]

The encryption key is auto-discovered from the app config (``AppConfig.credential_encryption_key``)
when ``--encryption-key`` is not explicitly provided, so you rarely need to pass it manually.
"""
import argparse
import binascii
import logging
import os
from base64 import urlsafe_b64decode
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import pymongo

from cryptography.fernet import InvalidToken
from global_utils.utils.crypto import FieldCipher, FERNET_PREFIX
from mas.catalog.element_registry import ElementRegistry
from mas.core.enums import ResourceCategory
from mas.resources.field_encryption import ResourceFieldEncryption

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _auto_discover_encryption_key() -> str:
    """Try to load the encryption key from the same sources the app uses.

    Resolution order (first non-empty wins):
    1. ``AppConfig().credential_encryption_key`` (pydantic-settings: env +
       .env + yaml + json — same loader the running app uses).
    2. ``$CREDENTIAL_ENCRYPTION_KEY`` env var (direct check, in case
       pydantic-settings didn't load it).
    3. ``credential_encryption_key`` from ``.env`` in CWD (direct dotenv
       read, in case the env var isn't exported but .env has it).
    4. ``$ENCRYPTION_KEY`` env var (legacy / backward-compat name).

    Returns ``""`` if nothing is found.
    """
    try:
        from config.app_config import AppConfig
        key = AppConfig().credential_encryption_key
        if key:
            logger.info("Auto-discovered encryption key from AppConfig.")
            return key
    except Exception:
        pass
    for var in ("CREDENTIAL_ENCRYPTION_KEY", "ENCRYPTION_KEY"):
        key = os.environ.get(var, "")
        if key:
            logger.info("Using encryption key from $%s.", var)
            return key
    try:
        from pathlib import Path
        from dotenv import dotenv_values
        env_path = Path(".env")
        if env_path.exists():
            vals = dotenv_values(env_path)
            key = vals.get("credential_encryption_key", "")
            if key:
                logger.info("Auto-discovered encryption key from .env file.")
                return key
    except Exception:
        pass
    return ""

FERNET_VERSION_BYTE = 0x80
FERNET_MIN_RAW_LENGTH = 73  # 1 (version) + 8 (timestamp) + 16 (IV) + 16 (min ciphertext) + 32 (HMAC)
FERNET_MIN_ENCODED_LENGTH = 100  # ceil(FERNET_MIN_RAW_LENGTH * 4/3), base64-encoded minimum


def run_migration(db_name: str, mongodb_ip: str, mongodb_port: str, dry_run: bool, reverse: bool = False, encryption_key: str = "", mongodb_uri: str = "") -> None:
    if mongodb_uri:
        client = pymongo.MongoClient(mongodb_uri)
    else:
        client = pymongo.MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
    cipher = FieldCipher(encryption_key) if encryption_key else None
    try:
        if reverse:
            _run_reverse_migration_body(client, db_name, dry_run, cipher)
        else:
            _run_migration_body(client, db_name, dry_run, cipher)
    finally:
        client.close()


def _run_migration_body(client: pymongo.MongoClient, db_name: str, dry_run: bool, cipher: Optional[FieldCipher] = None) -> None:
    db = client[db_name]
    resources_col = db["resources"]
    user_configs_col = db["builtin_user_configs"]

    sensitive_keys_cache: dict = {}

    if cipher:
        registry = ElementRegistry()
        registry.auto_discover()
        field_enc = ResourceFieldEncryption(registry, cipher)
    else:
        registry = None
        field_enc = None

    def _get_sensitive_keys(category: str, type_key: str) -> set:
        """Resolve sensitive field names for a (category, type_key) pair."""
        cache_key = (category, type_key)
        if cache_key in sensitive_keys_cache:
            return sensitive_keys_cache[cache_key]

        keys: set = set()
        if field_enc and registry:
            try:
                _, sensitive = field_enc.scan_schema_hints(category, type_key)
                model_cls = registry.get_schema(ResourceCategory(category), type_key)
                keys = sensitive | set(getattr(model_cls, "ENCRYPTED_FIELDS", ()))
            except (KeyError, ImportError, ValueError) as exc:
                raise RuntimeError(
                    f"Cannot resolve sensitive keys for {category}/{type_key} "
                    f"while encryption is enabled — aborting to prevent "
                    f"plaintext migration: {exc}"
                ) from exc
        sensitive_keys_cache[cache_key] = keys
        return keys

    def _encrypt_fields(fields: dict, sensitive_keys: set) -> dict:
        """Encrypt sensitive values, skipping already-encrypted ones."""
        if not cipher or not sensitive_keys:
            return fields
        result = {}
        for k, v in fields.items():
            if k in sensitive_keys and v and isinstance(v, str) and not v.startswith(FERNET_PREFIX):
                result[k] = cipher.encrypt(v)
            else:
                result[k] = v
        return result

    now = datetime.now(timezone.utc)

    # --- Step 1 & 2: Set ownership and visibility on all resources ---
    logger.info("Step 1: Migrating ownership and visibility fields...")

    builtin_docs = list(resources_col.find({"builtin_status": {"$exists": True, "$ne": None}}))
    custom_count = resources_col.count_documents({
        "$or": [
            {"builtin_status": None},
            {"builtin_status": {"$exists": False}},
        ]
    })

    logger.info("  Found %d built-in resources, %d custom resources", len(builtin_docs), custom_count)

    if not dry_run:
        resources_col.update_many(
            {"$or": [{"builtin_status": None}, {"builtin_status": {"$exists": False}}]},
            {"$set": {"ownership": "custom", "visibility": "draft"}},
        )

        for doc in builtin_docs:
            visibility = "public" if doc.get("builtin_status") == "public" else "draft"
            resources_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"ownership": "builtin", "visibility": visibility}},
            )

    if not dry_run:
        logger.info("  Done. Set ownership on %d documents.", len(builtin_docs) + custom_count)
    else:
        logger.info("  [DRY RUN] Would set ownership on %d documents.", len(builtin_docs) + custom_count)

    # --- Step 3: Migrate user_configs to builtin_user_configs collection ---
    logger.info("Step 2: Migrating embedded user_configs to builtin_user_configs collection...")

    migrated_configs = 0
    for doc in builtin_docs:
        user_configs = doc.get("user_configs", {})
        if not user_configs:
            continue

        resource_id = doc["_id"]
        category = doc.get("category", "")
        type_key = doc.get("type", "")
        sensitive_keys = _get_sensitive_keys(category, type_key)
        # Legacy per-resource allow-list of overridable field names. Only
        # migrate values for fields still on this list — carrying over
        # stale/no-longer-configurable keys would let them silently
        # override the current cfg_dict at resolve() time.
        configurable_keys = set(doc.get("configurable_keys") or [])

        for identity_key, config_values in user_configs.items():
            fields = {}
            for field_name, value in config_values.items():
                if value is None:
                    continue
                if configurable_keys and field_name not in configurable_keys:
                    continue
                fields[field_name] = value

            fields = _encrypt_fields(fields, sensitive_keys)

            # ``_id`` must match ``config_id`` — MongoBuiltinUserConfigRepository
            # stores/looks up documents by ``_id`` = ``config_id`` (see
            # ``save``/``get_by_id``); using two independently generated
            # UUIDs here would make migrated overlays permanently
            # unreachable via ``get_by_id()``.
            config_id = uuid4().hex
            user_config_doc = {
                "_id": config_id,
                "config_id": config_id,
                "resource_id": resource_id,
                "identity_key": identity_key,
                "fields": fields,
                "created": now,
                "updated": now,
            }

            if not dry_run:
                user_configs_col.replace_one(
                    {"resource_id": resource_id, "identity_key": identity_key},
                    user_config_doc,
                    upsert=True,
                )
            migrated_configs += 1

    logger.info("  Done. Migrated %d user config entries.", migrated_configs)

    # --- Step 4: Remove legacy fields ---
    logger.info("Step 3: Removing legacy fields (builtin_status, configurable_keys, user_configs)...")

    if not dry_run:
        result = resources_col.update_many(
            {},
            {"$unset": {
                "builtin_status": "",
                "configurable_keys": "",
                "user_configs": "",
            }},
        )
        logger.info("  Done. Updated %d documents.", result.modified_count)
    else:
        total = resources_col.count_documents({})
        logger.info("  [DRY RUN] Would update %d documents.", total)

    # --- Create indexes on new collections ---
    if not dry_run:
        logger.info("Step 4: Ensuring indexes on builtin_user_configs...")
        user_configs_col.create_index(
            [("resource_id", 1), ("identity_key", 1)],
            unique=True,
            name="uq_resource_identity",
        )
        user_configs_col.create_index("identity_key")
        logger.info("  Done.")

    logger.info("Migration complete%s.", " (DRY RUN)" if dry_run else "")


def _run_reverse_migration_body(client: pymongo.MongoClient, db_name: str, dry_run: bool, cipher: Optional[FieldCipher] = None) -> None:
    db = client[db_name]
    resources_col = db["resources"]
    user_configs_col = db["builtin_user_configs"]

    # --- Step 1: Restore embedded user_configs from builtin_user_configs collection ---
    logger.info("Step 1: Restoring embedded user_configs from builtin_user_configs...")

    def _is_fernet_token(value: str) -> bool:
        """Stricter check than prefix alone — validates structural properties
        of a Fernet token to avoid false-positives on user-provided values."""
        if not value.startswith(FERNET_PREFIX):
            return False
        if len(value) < FERNET_MIN_ENCODED_LENGTH or len(value) % 4 != 0:
            return False
        try:
            raw = urlsafe_b64decode(value)
            return len(raw) >= FERNET_MIN_RAW_LENGTH and raw[0] == FERNET_VERSION_BYTE
        except (binascii.Error, ValueError):
            return False

    def _decrypt_fields(fields: dict, resource_id: str = "", identity_key: str = "") -> dict:
        if not isinstance(fields, dict):
            raise ValueError(
                f"Overlay {resource_id}/{identity_key} has non-dict fields "
                f"(got {type(fields).__name__}) — skipping to avoid data corruption"
            )

        def _walk(value: object) -> object:
            if isinstance(value, str):
                if _is_fernet_token(value):
                    if not cipher:
                        raise RuntimeError(
                            f"Overlay {resource_id}/{identity_key} contains "
                            f"encrypted value but no --encryption-key was "
                            f"provided — aborting reverse migration"
                        )
                    return cipher.decrypt(value)
                return value
            if isinstance(value, dict):
                return {k: _walk(v) for k, v in value.items()}
            if isinstance(value, list):
                return [_walk(item) for item in value]
            return value

        return _walk(fields)

    user_configs_by_resource: dict = {}
    for cfg_doc in user_configs_col.find({}):
        resource_id = cfg_doc["resource_id"]
        identity_key = cfg_doc["identity_key"]
        raw_fields = cfg_doc.get("fields", {})
        if not isinstance(raw_fields, dict):
            raise ValueError(
                f"Overlay {resource_id}/{identity_key} has non-dict fields "
                f"(got {type(raw_fields).__name__}) — aborting before legacy "
                f"data is modified"
            )
        try:
            fields = _decrypt_fields(raw_fields, resource_id, identity_key)
        except InvalidToken as exc:
            raise RuntimeError(
                f"Failed to decrypt overlay {resource_id}/{identity_key} — "
                f"aborting before legacy data is modified: {exc}"
            ) from exc
        user_configs_by_resource.setdefault(resource_id, {})[identity_key] = fields

    total_configs = sum(len(v) for v in user_configs_by_resource.values())
    logger.info("  Found %d user config entries across %d resources.", total_configs, len(user_configs_by_resource))

    if not dry_run:
        for resource_id, user_configs in user_configs_by_resource.items():
            resources_col.update_one(
                {"_id": resource_id},
                {"$set": {"user_configs": user_configs}},
            )
        logger.info("  Done. Restored user_configs on %d resources.", len(user_configs_by_resource))
    else:
        logger.info("  [DRY RUN] Would restore user_configs on %d resources.", len(user_configs_by_resource))

    # --- Step 2: Restore builtin_status from ownership/visibility ---
    logger.info("Step 2: Restoring builtin_status field on built-in resources...")

    builtin_docs = list(resources_col.find({"ownership": "builtin"}))
    custom_count = resources_col.count_documents({"ownership": "custom"})

    logger.info(
        "  Found %d built-in resources, %d custom resources. Note: non-public builtin_status"
        " values collapse to 'draft' and cannot be fully recovered.",
        len(builtin_docs), custom_count,
    )

    if not dry_run:
        for doc in builtin_docs:
            builtin_status = "public" if doc.get("visibility") == "public" else "draft"
            resources_col.update_one(
                {"_id": doc["_id"]},
                {"$set": {"builtin_status": builtin_status}},
            )
        logger.info("  Done. Set builtin_status on %d documents.", len(builtin_docs))
    else:
        logger.info("  [DRY RUN] Would set builtin_status on %d documents.", len(builtin_docs))

    # --- Step 3: Remove ownership/visibility fields ---
    logger.info("Step 3: Removing ownership and visibility fields...")

    if not dry_run:
        result = resources_col.update_many(
            {},
            {"$unset": {"ownership": "", "visibility": ""}},
        )
        logger.info("  Done. Updated %d documents.", result.modified_count)
    else:
        total = resources_col.count_documents({})
        logger.info("  [DRY RUN] Would update %d documents.", total)

    # --- Step 4: Drop builtin_user_configs collection ---
    logger.info("Step 4: Dropping builtin_user_configs collection...")

    if not dry_run:
        user_configs_col.drop()
        logger.info("  Done.")
    else:
        logger.info("  [DRY RUN] Would drop builtin_user_configs collection (%d docs).", user_configs_col.count_documents({}))

    logger.info("Reverse migration complete%s.", " (DRY RUN)" if dry_run else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate to builtin ownership system")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument(
        "--reverse", action="store_true",
        help="Reverse the migration: restore builtin_status/user_configs, drop ownership/visibility",
    )
    parser.add_argument("--mongodb-ip", default="localhost")
    parser.add_argument("--mongodb-port", default="27017")
    parser.add_argument(
        "--mongodb-uri", default="",
        help="Full MongoDB URI (e.g. mongodb+srv://user:pass@host/db?tls=true). "
             "When provided, --mongodb-ip and --mongodb-port are ignored.",
    )
    parser.add_argument("--db-name", default="UnifAI")
    parser.add_argument(
        "--encryption-key",
        default=None,
        help=(
            "Fernet encryption key for encrypting/decrypting sensitive overlay "
            "fields.  When omitted, the key is auto-discovered from AppConfig "
            "(credential_encryption_key) or $CREDENTIAL_ENCRYPTION_KEY / "
            "$ENCRYPTION_KEY env vars."
        ),
    )
    args = parser.parse_args()

    encryption_key = args.encryption_key if args.encryption_key is not None else _auto_discover_encryption_key()

    run_migration(
        db_name=args.db_name,
        mongodb_ip=args.mongodb_ip,
        mongodb_port=args.mongodb_port,
        dry_run=args.dry_run,
        reverse=args.reverse,
        encryption_key=encryption_key,
        mongodb_uri=args.mongodb_uri,
    )
