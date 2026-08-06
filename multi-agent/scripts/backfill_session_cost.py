#!/usr/bin/env python3
"""
One-time migration: stamp every session in workflow_sessions with
total_cost=None and cost_updated_at="2026-07-31T00:00:00" so that
the lazy backfill in SessionService._backfill_cost only queries
Langfuse for sessions whose last_active_at is after that date.

Usage:
    # Dry run (default) — reports what would be updated
    python backfill_session_cost.py

    # Apply changes
    python backfill_session_cost.py --apply

    # Custom connection
    python backfill_session_cost.py --host 10.0.0.5 --port 27017 --db MyDB
"""
import argparse
from pymongo import MongoClient

COST_TRACKING_START = "2026-07-31T00:00:00"
COLLECTION = "workflow_sessions"


def main():
    parser = argparse.ArgumentParser(description="Backfill session cost fields")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default="27017")
    parser.add_argument("--db", default="UnifAI")
    parser.add_argument("--collection", default=COLLECTION)
    args = parser.parse_args()

    client = MongoClient(f"mongodb://{args.host}:{args.port}/")
    col = client[args.db][args.collection]

    total = col.count_documents({})
    already_stamped = col.count_documents({"metadata.cost_updated_at": {"$exists": True}})
    to_update = col.count_documents({"metadata.cost_updated_at": {"$exists": False}})

    print(f"Database:        {args.db}")
    print(f"Collection:      {args.collection}")
    print(f"Total sessions:  {total}")
    print(f"Already stamped: {already_stamped}")
    print(f"To update:       {to_update}")
    print(f"Stamp value:     cost_updated_at={COST_TRACKING_START}, total_cost=None")
    print()

    if to_update == 0:
        print("Nothing to do.")
        return

    if not args.apply:
        print("DRY RUN — no changes made. Pass --apply to execute.")
        return

    result = col.update_many(
        {"metadata.cost_updated_at": {"$exists": False}},
        {"$set": {
            "metadata.total_cost": None,
            "metadata.cost_updated_at": COST_TRACKING_START,
        }},
    )
    print(f"Updated {result.modified_count} sessions.")


if __name__ == "__main__":
    main()
