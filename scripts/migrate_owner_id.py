#!/usr/bin/env python3
"""
Migration Script: Backfill metadata.owner_id on existing Qdrant vectors.

Reads upload_by from MongoDB data_sources.sources, maps source_id -> upload_by,
then scrolls Qdrant collections and sets metadata.owner_id on each point.

Points with unmapped source_id get owner_id="unknown".

The script is **idempotent** — safe to re-run. set_payload uses dot-notation
to update only the owner_id field (preserves other metadata fields), and
create_payload_index is a no-op if the index already exists.

Usage:
    # Dry run (default)
    python scripts/migrate_owner_id.py

    # Apply
    python scripts/migrate_owner_id.py --apply

    # Specific collections
    python scripts/migrate_owner_id.py --apply --collections document_data slack_data

    # Custom batch size
    python scripts/migrate_owner_id.py --apply --batch-size 200

    # Audit: list unmapped source_ids that would get owner_id="unknown"
    python scripts/migrate_owner_id.py --audit-unknowns

Environment:
    MONGODB_IP       (default: localhost)
    MONGODB_PORT     (default: 27017)
    QDRANT_URL       (required)
    QDRANT_API_KEY   (default: "")
"""

import argparse
import os
import sys

import pymongo
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PayloadSchemaType,
    PointIdsList,
)


# ────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────

MONGODB_IP = os.environ.get("MONGODB_IP", "localhost")
MONGODB_PORT = os.environ.get("MONGODB_PORT", "27017")
SOURCES_DB = "data_sources"
SOURCES_COLLECTION = "sources"

QDRANT_URL = os.environ.get("QDRANT_URL")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_PORT = 80
QDRANT_TIMEOUT = 60.0

DEFAULT_COLLECTIONS = ["document_data", "slack_data"]


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def build_owner_map(mongo_col) -> dict:
    """Build source_id -> upload_by lookup from MongoDB."""
    owner_map = {}
    for doc in mongo_col.find({}, {"source_id": 1, "upload_by": 1}):
        sid = doc.get("source_id")
        owner = doc.get("upload_by")
        if sid and owner:
            owner_map[sid] = owner
    return owner_map


def audit_unknowns(
    qdrant: QdrantClient,
    collection_name: str,
    owner_map: dict,
    batch_size: int,
) -> dict:
    """Scroll a collection and report which source_ids have no owner mapping."""
    unmapped: dict[str, int] = {}
    total_points = 0
    offset = None

    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
        )

        if not points:
            break

        total_points += len(points)
        for point in points:
            source_id = point.payload.get("metadata", {}).get("source_id", "")
            if source_id not in owner_map:
                unmapped[source_id] = unmapped.get(source_id, 0) + 1

        if next_offset is None:
            break
        offset = next_offset

    return {"total_points": total_points, "unmapped_sources": unmapped}


# ────────────────────────────────────────────────────────────────
# Migration
# ────────────────────────────────────────────────────────────────

def _verify_batch(qdrant: QdrantClient, collection_name: str,
                   point_ids: list, expected_owner_id: str,
                   sample_size: int = 3) -> None:
    """Read back a sample of updated points and assert owner_id is set."""
    sample_ids = point_ids[:sample_size]
    points = qdrant.retrieve(
        collection_name=collection_name,
        ids=sample_ids,
        with_payload=True,
    )
    for point in points:
        actual = point.payload.get("metadata", {}).get("owner_id")
        if actual != expected_owner_id:
            raise RuntimeError(
                f"Verification failed for point {point.id} in {collection_name}: "
                f"expected metadata.owner_id={expected_owner_id!r}, "
                f"got {actual!r}. "
                f"The set_payload dot-notation may not be updating the nested "
                f"field as expected. Aborting migration."
            )


def migrate_collection(
    qdrant: QdrantClient,
    collection_name: str,
    owner_map: dict,
    batch_size: int,
    dry_run: bool,
    verify: bool = True,
) -> dict:
    stats = {"scrolled": 0, "updated": 0, "unknown": 0, "errors": []}

    # Create index (idempotent)
    if not dry_run:
        try:
            qdrant.create_payload_index(
                collection_name=collection_name,
                field_name="metadata.owner_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            print(f"  Created metadata.owner_id index on {collection_name}")
        except Exception as e:
            print(f"  Index may already exist: {e}")
    else:
        print(f"  [DRY RUN] Would create metadata.owner_id index on {collection_name}")

    # Scroll and batch update
    offset = None
    batch_num = 0

    while True:
        points, next_offset = qdrant.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
        )

        if not points:
            break

        stats["scrolled"] += len(points)
        batch_num += 1

        # Group point IDs by resolved owner_id for batch updates
        owner_groups: dict[str, list] = {}
        for point in points:
            source_id = point.payload.get("metadata", {}).get("source_id", "")
            owner_id = owner_map.get(source_id, "unknown")
            if owner_id == "unknown":
                stats["unknown"] += 1
            owner_groups.setdefault(owner_id, []).append(point.id)

        if dry_run:
            for owner_id, point_ids in owner_groups.items():
                print(f"    [DRY RUN] Batch {batch_num}: "
                      f"would set owner_id={owner_id!r} on {len(point_ids)} points")
            stats["updated"] += len(points)
        else:
            for owner_id, point_ids in owner_groups.items():
                try:
                    qdrant.set_payload(
                        collection_name=collection_name,
                        payload={"metadata.owner_id": owner_id},
                        points=PointIdsList(points=point_ids),
                    )
                    stats["updated"] += len(point_ids)

                    if verify and batch_num == 1:
                        _verify_batch(qdrant, collection_name,
                                      point_ids, owner_id)
                        print(f"    ✓ Verified metadata.owner_id on sample points")
                        verify = False
                except Exception as e:
                    stats["errors"].append(
                        f"Batch {batch_num}, owner={owner_id}: {e}"
                    )

        if batch_num % 10 == 0:
            print(f"    Progress: {stats['scrolled']} points scrolled, "
                  f"{stats['updated']} updated")

        if next_offset is None:
            break
        offset = next_offset

    return stats


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Backfill metadata.owner_id on Qdrant vectors (idempotent).",
    )
    parser.add_argument("--apply", action="store_true",
                        help="Apply changes (default is dry-run)")
    parser.add_argument("--audit-unknowns", action="store_true",
                        help="List unmapped source_ids that would get owner_id='unknown'")
    parser.add_argument("--collections", nargs="*", default=None,
                        help=f"Collections to migrate (default: {DEFAULT_COLLECTIONS})")
    parser.add_argument("--batch-size", type=int, default=100,
                        help="Points per scroll batch (default: 100)")
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip postcondition verification of first batch")
    args = parser.parse_args()

    dry_run = not args.apply
    collections = args.collections or DEFAULT_COLLECTIONS

    if not QDRANT_URL:
        print("ERROR: QDRANT_URL environment variable is required")
        sys.exit(1)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE — no changes will be made")
        print("Use --apply to actually apply changes")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("APPLYING CHANGES")
        print("=" * 60)

    # Connect
    mongo_uri = f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/"
    print(f"\nMongoDB: {mongo_uri} / {SOURCES_DB}.{SOURCES_COLLECTION}")
    print(f"Qdrant:  {QDRANT_URL}")
    print(f"Collections: {collections}")
    print(f"Batch size: {args.batch_size}")

    mongo_client = pymongo.MongoClient(mongo_uri)
    sources_col = mongo_client[SOURCES_DB][SOURCES_COLLECTION]

    qdrant = QdrantClient(
        url=QDRANT_URL, port=QDRANT_PORT,
        api_key=QDRANT_API_KEY, timeout=QDRANT_TIMEOUT,
    )

    # Build lookup
    owner_map = build_owner_map(sources_col)
    print(f"\nLoaded {len(owner_map)} source_id -> upload_by mappings from MongoDB")

    # Audit mode: report unknowns and exit
    if args.audit_unknowns:
        print(f"\n{'=' * 60}")
        print("AUDIT: Scanning for unmapped source_ids")
        print(f"{'=' * 60}")

        for coll in collections:
            print(f"\n  Collection: {coll}")
            result = audit_unknowns(qdrant, coll, owner_map, args.batch_size)
            total_points = result["total_points"]
            unmapped = result["unmapped_sources"]
            unknown_points = sum(unmapped.values())

            if not unmapped:
                print(f"    All {total_points} points have a valid owner mapping.")
            else:
                pct = (unknown_points / total_points * 100) if total_points else 0
                print(f"    {unknown_points}/{total_points} points ({pct:.1f}%) "
                      f"would be flagged as 'unknown'")
                print(f"    Unmapped source_ids ({len(unmapped)} distinct):")
                for sid, count in sorted(unmapped.items(), key=lambda x: -x[1]):
                    print(f"      {sid or '(empty)':<40} → {count} points")

        mongo_client.close()
        return 0

    # Migrate each collection
    total = {"scrolled": 0, "updated": 0, "unknown": 0, "errors": []}

    for coll in collections:
        print(f"\n{'=' * 60}")
        print(f"COLLECTION: {coll}")
        print(f"{'=' * 60}")

        stats = migrate_collection(qdrant, coll, owner_map, args.batch_size, dry_run,
                                   verify=not args.no_verify)

        for key in ("scrolled", "updated", "unknown"):
            total[key] += stats[key]
        total["errors"].extend(stats["errors"])

        print(f"\n  {coll}: {stats['scrolled']} scrolled, "
              f"{stats['updated']} updated, {stats['unknown']} unknown")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Points scrolled:    {total['scrolled']}")
    print(f"  {'Would update' if dry_run else 'Updated'}:       {total['updated']}")
    print(f"  Unknown owner:      {total['unknown']}")
    if total["errors"]:
        print(f"  Errors:             {len(total['errors'])}")
        for err in total["errors"]:
            print(f"    - {err}")

    if dry_run:
        print(f"\nThis was a DRY RUN. Use --apply to make changes.")
    else:
        print(f"\nMigration complete!")

    mongo_client.close()
    return 0 if not total["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
