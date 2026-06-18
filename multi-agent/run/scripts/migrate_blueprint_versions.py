#!/usr/bin/env python3
"""
Migration script: Backfill GENIE-1336 blueprint versioning fields.

This script is **idempotent** — running it multiple times produces the
same final state without creating duplicate data or raising errors.

Steps
-----
1. ``step1_backfill_version_field``
   For every document in ``blueprints`` that does NOT have a ``version``
   field, set ``version = 1`` via a bulk_write with ``$set`` and a filter
   of ``{"version": {"$exists": false}}``.

2. ``step2_insert_initial_snapshots``
   For every blueprint in ``blueprints``, upsert a version-1 snapshot in
   ``blueprint_versions`` using ``$setOnInsert`` so that already-existing
   snapshots are left untouched.

Usage
-----
    python scripts/migrate_blueprint_versions.py \\
        --mongo-uri mongodb://localhost:27017 \\
        --db-name mas \\
        --batch-size 100

    # Dry-run (reads only, no writes):
    python scripts/migrate_blueprint_versions.py --dry-run
"""

from __future__ import annotations

import argparse
import copy
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List

import pymongo
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError
from pymongo.operations import UpdateOne


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATION_USER: str = "migration/GENIE-1336"
_CHANGE_SUMMARY: str = "Initial snapshot created by GENIE-1336 migration"


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _batch(iterable: Iterator[Any], size: int) -> Iterator[List[Any]]:
    """Yield successive chunks of ``size`` items from ``iterable``."""
    batch: List[Any] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


# ---------------------------------------------------------------------------
# Core migration function
# ---------------------------------------------------------------------------


def _migrate(
    blueprints_col: Collection,
    versions_col: Collection,
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """
    Run both migration steps and return the total error count (0 = clean).

    Steps
    -----
    1. Set ``version = 1`` on every blueprint document that lacks a
       ``version`` field.
    2. For each blueprint that does NOT already have a v1 snapshot in
       ``blueprint_versions``, insert one via upsert.

    Parameters
    ----------
    blueprints_col:
        PyMongo collection for ``blueprints``.
    versions_col:
        PyMongo collection for ``blueprint_versions``.
    batch_size:
        Controls both the cursor ``batch_size`` and the bulk-write batch
        chunking.
    dry_run:
        When ``True``, no writes are performed.

    Returns
    -------
    int
        Total number of write errors encountered (0 = success).
    """
    total_errors = 0

    # Read all blueprints.
    all_docs: List[Dict[str, Any]] = list(
        blueprints_col.find({}).batch_size(batch_size)
    )

    if dry_run:
        return 0

    # ── Step 1: backfill version=1 on docs without a ``version`` key ──
    step1_ops: List[UpdateOne] = []
    for doc in all_docs:
        if "version" not in doc:
            step1_ops.append(
                UpdateOne(
                    {"blueprint_id": doc["blueprint_id"]},
                    {"$set": {"version": 1}},
                )
            )

    if step1_ops:
        blueprints_col.bulk_write(step1_ops)

    # ── Step 2: insert initial v1 snapshots ──
    existing_v1 = {
        d["blueprint_id"]
        for d in versions_col.find({"version": 1}, {"blueprint_id": 1})
    }

    step2_ops: List[UpdateOne] = []
    for doc in all_docs:
        bp_id = doc["blueprint_id"]
        if bp_id in existing_v1:
            continue
        step2_ops.append(
            UpdateOne(
                {"blueprint_id": bp_id, "version": 1},
                {
                    "$setOnInsert": {
                        "blueprint_id": bp_id,
                        "version": 1,
                        "spec_dict_snapshot": doc.get("spec_dict", {}),
                        "created_by": _MIGRATION_USER,
                        "created_at": doc.get(
                            "created_at", datetime.now(timezone.utc)
                        ),
                        "change_summary": _CHANGE_SUMMARY,
                    }
                },
                upsert=True,
            )
        )

    for batch_ops in _batch(iter(step2_ops), batch_size):
        try:
            versions_col.bulk_write(batch_ops)
        except BulkWriteError as exc:
            total_errors += len(exc.details.get("writeErrors", []))

    return total_errors


# ---------------------------------------------------------------------------
# Step 1: backfill ``version`` field on blueprints
# ---------------------------------------------------------------------------


def step1_backfill_version_field(
    bp_col: Collection,
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """
    Set ``version = 1`` on all blueprints that do not yet have the field.

    Returns the number of documents modified.
    """
    filter_missing = {"version": {"$exists": False}}
    total_modified = 0

    if dry_run:
        count = bp_col.count_documents(filter_missing)
        print(f"[DRY-RUN] Step 1: would backfill version=1 on {count} blueprints.")
        return count

    # Use a single bulk-write with UpdateMany for efficiency.
    result = bp_col.update_many(
        filter_missing,
        {"$set": {"version": 1}},
    )
    total_modified = result.modified_count
    print(f"Step 1 complete: set version=1 on {total_modified} blueprints.")
    return total_modified


# ---------------------------------------------------------------------------
# Step 2: upsert initial snapshots into blueprint_versions
# ---------------------------------------------------------------------------


def step2_insert_initial_snapshots(
    bp_col: Collection,
    bpv_col: Collection,
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """
    For each blueprint, upsert a v1 snapshot in ``blueprint_versions``
    using ``$setOnInsert`` so that existing snapshots are never overwritten.

    Processes blueprints in batches to support very large collections without
    holding all documents in memory.

    Returns the number of upserts performed (new snapshots created).
    """
    total_upserted = 0

    # Project only the fields we need for the snapshot.
    projection = {
        "blueprint_id": 1,
        "spec_dict": 1,
        "created_at": 1,
    }
    cursor = bp_col.find({}, projection)

    for batch_docs in _batch(iter(cursor), batch_size):
        if dry_run:
            total_upserted += len(batch_docs)
            continue

        for doc in batch_docs:
            blueprint_id = doc["blueprint_id"]
            # Deep-copy so mutations to the source doc can never affect the snapshot.
            spec_dict = copy.deepcopy(doc.get("spec_dict", {}))
            created_at = doc.get("created_at")
            if created_at is None:
                created_at = datetime.now(timezone.utc)

            filter_query = {"blueprint_id": blueprint_id, "version": 1}

            # Count before/after to reliably detect new insertions
            # (mongomock's bulk_write result.upserted_count is unreliable).
            count_before = bpv_col.count_documents(filter_query)
            bpv_col.update_one(
                filter_query,
                {
                    "$setOnInsert": {
                        "blueprint_id": blueprint_id,
                        "version": 1,
                        "spec_dict_snapshot": spec_dict,
                        "created_by": "migration/GENIE-1336",
                        "created_at": created_at,
                        "change_summary": "Initial snapshot created by GENIE-1336 migration",
                    }
                },
                upsert=True,
            )
            count_after = bpv_col.count_documents(filter_query)
            if count_after > count_before:
                total_upserted += 1

    if dry_run:
        print(f"[DRY-RUN] Step 2: would upsert initial snapshots for {total_upserted} blueprints.")
    else:
        print(f"Step 2 complete: inserted {total_upserted} new initial snapshots.")

    return total_upserted


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------


def ensure_version_indexes(bpv_col: Collection, dry_run: bool = False) -> None:
    """Create indexes on ``blueprint_versions`` if they don't already exist."""
    if dry_run:
        print("[DRY-RUN] Would ensure indexes on blueprint_versions.")
        return

    from pymongo import ASCENDING, DESCENDING

    bpv_col.create_index(
        [("blueprint_id", ASCENDING), ("version", ASCENDING)],
        unique=True,
        name="bp_version_unique",
    )
    bpv_col.create_index(
        [("blueprint_id", ASCENDING), ("version", DESCENDING)],
        name="bp_version_desc",
    )
    bpv_col.create_index(
        [("blueprint_id", ASCENDING), ("created_at", DESCENDING)],
        name="bp_created_at_desc",
    )
    print("Indexes ensured on blueprint_versions.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill GENIE-1336 versioning fields into blueprints and blueprint_versions."
    )
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="PyMongo connection string (default: mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--db-name",
        default="mas",
        help="Database name (default: mas)",
    )
    parser.add_argument(
        "--blueprint-coll",
        default="blueprints",
        help="Blueprints collection name (default: blueprints)",
    )
    parser.add_argument(
        "--versions-coll",
        default="blueprint_versions",
        help="Blueprint versions collection name (default: blueprint_versions)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of blueprints to process per batch (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making any changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    client = pymongo.MongoClient(args.mongo_uri)
    db = client[args.db_name]
    bp_col = db[args.blueprint_coll]
    bpv_col = db[args.versions_coll]

    print(
        f"Migration starting — db={args.db_name!r}, "
        f"blueprints={args.blueprint_coll!r}, "
        f"versions={args.versions_coll!r}, "
        f"batch_size={args.batch_size}, "
        f"dry_run={args.dry_run}"
    )

    try:
        # Ensure indexes first (idempotent).
        ensure_version_indexes(bpv_col, dry_run=args.dry_run)

        # Step 1: backfill version field on blueprints collection.
        step1_backfill_version_field(
            bp_col=bp_col,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        # Step 2: upsert initial v1 snapshots.
        step2_insert_initial_snapshots(
            bp_col=bp_col,
            bpv_col=bpv_col,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        print("Migration complete.")
        return 0
    except Exception as exc:
        print(f"Migration FAILED: {exc}", file=sys.stderr)
        raise
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
