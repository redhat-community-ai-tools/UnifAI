#!/usr/bin/env python3
"""
One-time migration: rename duplicate blueprint names so that
(identity.type, identity.id, spec_dict.name) is unique.

For every group of blueprints that share the same identity + name,
the oldest document keeps its name and newer duplicates get a " (2)",
" (3)", … suffix appended to spec_dict.name.

Usage:
  # Dry-run (default) — prints what would change, writes nothing:
  python scripts/migrate_duplicate_blueprint_names.py

  # Apply changes:
  python scripts/migrate_duplicate_blueprint_names.py --apply

Environment variables (same as the main app):
  MONGODB_IP   (default 127.0.0.1)
  MONGODB_PORT (default 27017)
  MONGO_DB     (default UnifAI)
"""

import os
import sys
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MULTI_AGENT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, MULTI_AGENT_ROOT)

import pymongo
from global_utils.utils.util import get_mongo_url


def run(apply: bool):
    client = pymongo.MongoClient(get_mongo_url())
    db_name = os.environ.get("MONGO_DB", "UnifAI")
    col = client[db_name]["blueprints"]

    pipeline = [
        {"$sort": {"created_at": 1}},
        {"$group": {
            "_id": {
                "identity_type": "$identity.type",
                "identity_id": "$identity.id",
                "name": "$spec_dict.name",
            },
            "count": {"$sum": 1},
            "docs": {"$push": {
                "blueprint_id": "$blueprint_id",
                "created_at": "$created_at",
            }},
        }},
        {"$match": {"count": {"$gt": 1}}},
        {"$sort": {"count": -1}},
    ]

    groups = list(col.aggregate(pipeline))

    if not groups:
        print("No duplicate blueprint names found. Nothing to do.")
        return

    total_renames = 0
    for g in groups:
        identity_id = g["_id"]["identity_id"]
        original_name = g["_id"]["name"]
        duplicates = g["docs"][1:]  # skip the oldest (keeps original name)

        print(f"\n  identity={identity_id}  name=\"{original_name}\"  "
              f"duplicates={len(duplicates)}")

        # Collect all existing names for this identity so we don't collide
        # with names that already exist outside this duplicate group.
        existing_names = set(
            doc["spec_dict"]["name"]
            for doc in col.find(
                {"identity.type": g["_id"]["identity_type"],
                 "identity.id": identity_id},
                {"spec_dict.name": 1},
            )
        )

        for dup in duplicates:
            counter = 2
            while True:
                candidate = f"{original_name} ({counter})"
                if candidate not in existing_names:
                    break
                counter += 1

            existing_names.add(candidate)
            bp_id = dup["blueprint_id"]

            if apply:
                col.update_one(
                    {"blueprint_id": bp_id},
                    {"$set": {"spec_dict.name": candidate}},
                )
                print(f"    RENAMED  {bp_id}  ->  \"{candidate}\"")
            else:
                print(f"    (dry-run) would rename {bp_id}  ->  \"{candidate}\"")

            total_renames += 1

    mode = "Applied" if apply else "Would apply"
    print(f"\n{mode} {total_renames} rename(s) across {len(groups)} duplicate group(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="Actually write changes (default is dry-run)")
    args = parser.parse_args()
    run(apply=args.apply)
