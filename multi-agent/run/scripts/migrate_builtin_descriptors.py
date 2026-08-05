"""
Migration script: extract built-in metadata off ``resources`` documents into
the separate ``builtin_resource_descriptors`` collection.

**Prerequisite:** ``migrate_builtin_system.py`` must have been run first —
it creates the ``ownership``/``visibility`` fields on ``resources`` documents
that this script reads.  Running this script before that one will silently
find zero built-in resources and produce an empty descriptor collection.

Follow-up to ``migrate_builtin_system.py`` (which introduced the
``ownership``/``visibility`` fields directly on ``resources`` documents —
left untouched, historical). This script decouples that concept: the
``BuiltinResourceDescriptor`` model now owns ``visibility``/
``parent_builtin_id`` in its own collection, joined to ``resources`` by
``rid``/``_id``. Existence of a descriptor *is* the "this resource is a
built-in" signal, so ``ownership`` itself no longer needs to be persisted
anywhere.

Steps performed:
1. Every ``resources`` doc with ``ownership="builtin"`` gets one
   ``builtin_resource_descriptors`` doc written (``visibility``,
   ``parent_builtin_id``, ``created``, ``updated``).
2. ``ownership``, ``visibility``, ``parent_builtin_id`` are ``$unset`` from
   every ``resources`` document (custom resources never had
   ``parent_builtin_id`` set, but the ``$unset`` is harmless if absent).

Reverse migration (--reverse):
1. For every ``builtin_resource_descriptors`` doc, ``$set`` ``ownership``,
   ``visibility``, ``parent_builtin_id`` back onto the matching
   ``resources`` document.
2. Every other ``resources`` document (no matching descriptor) gets
   ``ownership="custom"``.
3. The ``builtin_resource_descriptors`` collection is dropped.

Usage:
    python -m run.scripts.migrate_builtin_descriptors [--dry-run] [--reverse] [--mongodb-ip localhost] [--mongodb-port 27017] [--db-name UnifAI]
"""
import argparse
import logging

import pymongo

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_migration(db_name: str, mongodb_ip: str, mongodb_port: str, dry_run: bool, reverse: bool = False) -> None:
    client = pymongo.MongoClient(f"mongodb://{mongodb_ip}:{mongodb_port}/")
    try:
        if reverse:
            _run_reverse_migration_body(client, db_name, dry_run)
        else:
            _run_migration_body(client, db_name, dry_run)
    finally:
        client.close()


def _run_migration_body(client: pymongo.MongoClient, db_name: str, dry_run: bool) -> None:
    db = client[db_name]
    resources_col = db["resources"]
    descriptors_col = db["builtin_resource_descriptors"]

    logger.info("Step 1: Extracting built-in descriptors from resources...")

    builtin_docs = list(resources_col.find({"ownership": "builtin"}))
    logger.info("  Found %d built-in resources.", len(builtin_docs))

    written = 0
    for doc in builtin_docs:
        descriptor_doc = {
            "_id": doc["_id"],
            "rid": doc["_id"],
            "visibility": doc.get("visibility", "draft"),
            "parent_builtin_id": doc.get("parent_builtin_id"),
            "created": doc.get("created"),
            "updated": doc.get("updated"),
        }
        if not dry_run:
            descriptors_col.replace_one({"_id": doc["_id"]}, descriptor_doc, upsert=True)
        written += 1

    if not dry_run:
        logger.info("  Done. Wrote %d descriptor documents.", written)
    else:
        logger.info("  [DRY RUN] Would write %d descriptor documents.", written)

    logger.info("Step 2: Removing ownership/visibility/parent_builtin_id from resources...")

    if not dry_run:
        result = resources_col.update_many(
            {},
            {"$unset": {"ownership": "", "visibility": "", "parent_builtin_id": ""}},
        )
        logger.info("  Done. Updated %d documents.", result.modified_count)
    else:
        total = resources_col.count_documents({})
        logger.info("  [DRY RUN] Would update %d documents.", total)

    if not dry_run:
        logger.info("Step 3: Ensuring indexes on builtin_resource_descriptors...")
        descriptors_col.create_index("visibility", background=True)
        logger.info("  Done.")

    logger.info("Migration complete%s.", " (DRY RUN)" if dry_run else "")


def _run_reverse_migration_body(client: pymongo.MongoClient, db_name: str, dry_run: bool) -> None:
    db = client[db_name]
    resources_col = db["resources"]
    descriptors_col = db["builtin_resource_descriptors"]

    logger.info("Step 1: Restoring ownership/visibility/parent_builtin_id onto resources...")

    descriptor_docs = list(descriptors_col.find({}))
    logger.info("  Found %d built-in descriptors.", len(descriptor_docs))

    if not dry_run:
        for doc in descriptor_docs:
            update_fields = {
                "ownership": "builtin",
                "visibility": doc.get("visibility", "draft"),
            }
            if doc.get("parent_builtin_id") is not None:
                update_fields["parent_builtin_id"] = doc["parent_builtin_id"]
            resources_col.update_one(
                {"_id": doc["_id"]},
                {"$set": update_fields},
            )
        builtin_rids = {doc["_id"] for doc in descriptor_docs}
        result = resources_col.update_many(
            {"_id": {"$nin": list(builtin_rids)}},
            {"$set": {"ownership": "custom"}},
        )
        logger.info(
            "  Done. Restored %d built-in resources, set ownership=custom on %d others.",
            len(descriptor_docs), result.modified_count,
        )
    else:
        custom_count = resources_col.count_documents({"_id": {"$nin": [d["_id"] for d in descriptor_docs]}})
        logger.info(
            "  [DRY RUN] Would restore %d built-in resources, set ownership=custom on %d others.",
            len(descriptor_docs), custom_count,
        )

    logger.info("Step 2: Dropping builtin_resource_descriptors collection...")

    if not dry_run:
        descriptors_col.drop()
        logger.info("  Done.")
    else:
        logger.info(
            "  [DRY RUN] Would drop builtin_resource_descriptors collection (%d docs).",
            descriptors_col.count_documents({}),
        )

    logger.info("Reverse migration complete%s.", " (DRY RUN)" if dry_run else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract built-in resource metadata into builtin_resource_descriptors"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument(
        "--reverse", action="store_true",
        help="Reverse the migration: restore ownership/visibility/parent_builtin_id on resources, drop the descriptor collection",
    )
    parser.add_argument("--mongodb-ip", default="localhost")
    parser.add_argument("--mongodb-port", default="27017")
    parser.add_argument("--db-name", default="UnifAI")
    args = parser.parse_args()

    run_migration(
        db_name=args.db_name,
        mongodb_ip=args.mongodb_ip,
        mongodb_port=args.mongodb_port,
        dry_run=args.dry_run,
        reverse=args.reverse,
    )
