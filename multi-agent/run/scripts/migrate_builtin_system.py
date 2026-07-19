"""
Migration script: Transition from legacy builtin_status to the new ownership/visibility model.

Steps performed:
1. All existing resources with builtin_status != None get ownership="builtin" + visibility mapped.
2. All existing resources with builtin_status == None get ownership="custom".
3. Existing user_configs embedded on resources are migrated to the builtin_user_configs collection.
4. BuiltinSchema documents are generated from configurable_keys on existing resources.
5. Legacy fields (builtin_status, configurable_keys, user_configs) are removed from all documents.

Usage:
    python -m run.scripts.migrate_builtin_system [--dry-run] [--mongodb-ip localhost] [--mongodb-port 27017]
"""
import argparse
import logging
from datetime import datetime, timezone
from uuid import uuid4

import pymongo

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migration(db_name: str, mongodb_ip: str, mongodb_port: str, dry_run: bool):
    client = pymongo.MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
    db = client[db_name]
    resources_col = db["resources"]
    schemas_col = db["builtin_schemas"]
    user_configs_col = db["builtin_user_configs"]

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

    logger.info("  Done. Set ownership on %d documents.", len(builtin_docs) + custom_count)

    # --- Step 3: Migrate user_configs to builtin_user_configs collection ---
    logger.info("Step 2: Migrating embedded user_configs to builtin_user_configs collection...")

    migrated_configs = 0
    for doc in builtin_docs:
        user_configs = doc.get("user_configs", {})
        if not user_configs:
            continue

        resource_id = doc["_id"]
        configurable_keys = doc.get("configurable_keys", [])

        for identity_key, config_values in user_configs.items():
            fields = {}
            for field_name, value in config_values.items():
                if value is not None:
                    fields[field_name] = value

            user_config_doc = {
                "_id": uuid4().hex,
                "config_id": uuid4().hex,
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

    # --- Step 4: Generate BuiltinSchema documents from configurable_keys (per type) ---
    logger.info("Step 3: Generating builtin_schemas from configurable_keys (grouped by type)...")

    type_schemas = {}
    for doc in builtin_docs:
        configurable_keys = doc.get("configurable_keys", [])
        if not configurable_keys:
            continue

        category = doc.get("category")
        element_type = doc.get("type")
        type_key = (category, element_type)

        if type_key in type_schemas:
            continue

        cfg_dict = doc.get("cfg_dict", {})

        configurable_fields = []
        for key in configurable_keys:
            default_value = cfg_dict.get(key)
            field_type = _infer_field_type(default_value)
            configurable_fields.append({
                "field_name": key,
                "field_type": field_type,
                "required": False,
                "default": default_value,
                "description": "",
                "enum_options": [],
                "sensitive": field_type == "secret",
            })

        schema_doc = {
            "_id": uuid4().hex,
            "schema_id": uuid4().hex,
            "category": category,
            "element_type": element_type,
            "configurable_fields": configurable_fields,
            "discriminator_field": None,
            "variants": [],
            "created": now,
            "updated": now,
        }
        type_schemas[type_key] = schema_doc

    if not dry_run:
        for schema_doc in type_schemas.values():
            schemas_col.replace_one(
                {"category": schema_doc["category"], "element_type": schema_doc["element_type"]},
                schema_doc,
                upsert=True,
            )

    logger.info("  Done. Created %d builtin_schema documents (one per type).", len(type_schemas))

    # --- Step 5: Remove legacy fields ---
    logger.info("Step 4: Removing legacy fields (builtin_status, configurable_keys, user_configs)...")

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
        logger.info("Step 5: Ensuring indexes on new collections...")
        schemas_col.create_index(
            [("category", 1), ("element_type", 1)],
            unique=True,
            name="uq_category_element_type",
        )
        user_configs_col.create_index(
            [("resource_id", 1), ("identity_key", 1)],
            unique=True,
            name="uq_resource_identity",
        )
        user_configs_col.create_index("identity_key")
        logger.info("  Done.")

    logger.info("Migration complete%s.", " (DRY RUN)" if dry_run else "")


def _infer_field_type(value) -> str:
    if value is None or value == "":
        return "secret"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "string"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate to builtin ownership system")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--mongodb-ip", default="localhost")
    parser.add_argument("--mongodb-port", default="27017")
    parser.add_argument("--db-name", default="UnifAI")
    args = parser.parse_args()

    run_migration(
        db_name=args.db_name,
        mongodb_ip=args.mongodb_ip,
        mongodb_port=args.mongodb_port,
        dry_run=args.dry_run,
    )
