"""
One-time migration script — GENIE-1336: Blueprint Version History & Rollback
============================================================================

What this script does
---------------------
1. Iterates every document in the ``blueprints`` collection.
2. For documents that don't yet have the ``version`` field (or have it set to
   a value other than 1), it sets ``version = 1``.
3. For each blueprint that does NOT already have an entry in
   ``blueprint_versions`` for version 1, it inserts an initial snapshot so
   the version history timeline is complete from day one.

Idempotency
-----------
The script is safe to run multiple times:
* The ``blueprints`` update uses ``$set`` with ``{version: 1}`` only when
  the field is absent (``$exists: false``), leaving already-versioned docs
  alone.
* The version snapshot insert is guarded by ``update_one(..., upsert=True)``
  with the unique ``{blueprint_id, version}`` compound key — duplicate
  attempts silently no-op.

Running
-------
From the project root with the ``multi-agent`` venv activated::

    python run/scripts/migrate_blueprint_versions.py [--dry-run] [--batch-size N]

Options
~~~~~~~
--dry-run       Print what would be changed without touching the database.
--batch-size N  Number of blueprints to process per batch (default 100).
--mongo-uri U   Override the MongoDB URI (defaults to MONGO_URI env var or
                the global_utils helper).
--db-name D     Override the database name (default: UnifAI).

Exit codes
----------
0  Migration completed successfully (or nothing to do).
1  One or more documents failed — check stderr for details.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from typing import Iterator, List

import pymongo
from pymongo import UpdateOne, InsertOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError

from global_utils.utils.util import get_mongo_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("migrate_blueprint_versions")

_MIGRATION_USER = "migration-script"
_CHANGE_SUMMARY = "Initial version snapshot created by GENIE-1336 migration."


# ── Helpers ────────────────────────────────────────────────────────────────────


def _batch(iterable, size: int) -> Iterator[List]:
    """Yield successive fixed-size chunks from *iterable*."""
    batch: List = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _migrate(
    *,
    blueprints_col: Collection,
    versions_col: Collection,
    batch_size: int,
    dry_run: bool,
) -> int:
    """Core migration logic.

    Returns:
        Number of blueprints processed (0 when nothing was needed).
    """
    total_blueprints = blueprints_col.count_documents({})
    logger.info("Found %d blueprints in total.", total_blueprints)

    processed = 0
    errors = 0

    cursor = blueprints_col.find(
        {},
        {
            "blueprint_id": 1,
            "spec_dict": 1,
            "identity": 1,
            "version": 1,
            "created_at": 1,
        },
    ).batch_size(batch_size)

    for docs in _batch(cursor, batch_size):
        # ── Step 1: Set version=1 on blueprints that lack the field ─────────
        needs_version_set = [
            d["blueprint_id"] for d in docs if not d.get("version")
        ]
        if needs_version_set and not dry_run:
            blueprints_col.bulk_write(
                [
                    UpdateOne(
                        {"blueprint_id": bid, "version": {"$exists": False}},
                        {"$set": {"version": 1}},
                    )
                    for bid in needs_version_set
                ],
                ordered=False,
            )
        if needs_version_set:
            logger.info(
                "%s Set version=1 on %d blueprints: %s …",
                "[DRY-RUN]" if dry_run else "",
                len(needs_version_set),
                needs_version_set[:3],
            )

        # ── Step 2: Create initial version snapshots ─────────────────────────
        # Build the set of blueprint_ids that already have a v1 snapshot.
        blueprint_ids = [d["blueprint_id"] for d in docs]
        existing_v1 = {
            doc["blueprint_id"]
            for doc in versions_col.find(
                {"blueprint_id": {"$in": blueprint_ids}, "version": 1},
                {"blueprint_id": 1},
            )
        }

        snapshot_ops = []
        for doc in docs:
            bid = doc["blueprint_id"]
            if bid in existing_v1:
                continue  # Already snapshotted — skip.

            spec_dict = doc.get("spec_dict") or {}
            created_at = doc.get("created_at") or datetime.now(timezone.utc)

            snapshot_ops.append(
                UpdateOne(
                    # Upsert guard — unique compound index prevents doubles.
                    {"blueprint_id": bid, "version": 1},
                    {
                        "$setOnInsert": {
                            "blueprint_id": bid,
                            "version": 1,
                            "spec_dict_snapshot": spec_dict,
                            "created_by": _MIGRATION_USER,
                            "created_at": created_at,
                            "change_summary": _CHANGE_SUMMARY,
                        }
                    },
                    upsert=True,
                )
            )

        if snapshot_ops:
            if dry_run:
                logger.info(
                    "[DRY-RUN] Would insert %d initial version snapshots.",
                    len(snapshot_ops),
                )
            else:
                try:
                    result = versions_col.bulk_write(snapshot_ops, ordered=False)
                    logger.info(
                        "Inserted %d initial version snapshots (upserted: %d).",
                        len(snapshot_ops),
                        result.upserted_count,
                    )
                except BulkWriteError as bwe:
                    # Partial failure — log details but continue.
                    write_errors = bwe.details.get("writeErrors", [])
                    logger.error(
                        "BulkWriteError: %d errors in batch. Details: %s",
                        len(write_errors),
                        write_errors[:5],
                    )
                    errors += len(write_errors)

        processed += len(docs)
        logger.info("Progress: %d / %d blueprints processed.", processed, total_blueprints)

    if errors:
        logger.error("Migration finished with %d error(s).", errors)
    else:
        logger.info(
            "Migration completed successfully. %d blueprints processed.",
            processed,
        )

    return errors


# ── CLI entry-point ────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Back-fill version=1 and initial version snapshots for all existing blueprints."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would happen without modifying the database.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        dest="batch_size",
        help="Blueprints to process per batch (default: 100).",
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        default=None,
        dest="mongo_uri",
        help="MongoDB connection URI (overrides MONGO_URI env var).",
    )
    parser.add_argument(
        "--db-name",
        type=str,
        default="UnifAI",
        dest="db_name",
        help="MongoDB database name (default: UnifAI).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    mongo_uri = args.mongo_uri or get_mongo_url()
    logger.info(
        "Connecting to MongoDB%s (db=%s).",
        " [DRY-RUN — no writes]" if args.dry_run else "",
        args.db_name,
    )

    client = pymongo.MongoClient(mongo_uri)
    db = client[args.db_name]

    blueprints_col: Collection = db["blueprints"]
    versions_col: Collection = db["blueprint_versions"]

    # Ensure the unique index exists before we attempt upserts.
    logger.info("Ensuring indexes on blueprint_versions …")
    versions_col.create_index(
        [("blueprint_id", pymongo.ASCENDING), ("version", pymongo.ASCENDING)],
        unique=True,
        name="idx_blueprint_version_unique",
        background=True,
    )
    versions_col.create_index(
        [("blueprint_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        name="idx_blueprint_version_list",
        background=True,
    )

    error_count = _migrate(
        blueprints_col=blueprints_col,
        versions_col=versions_col,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
