#!/usr/bin/env python3
"""
Migration Script: Convert doc_ids field from string array to object array,
and rename the field from doc_ids to docs.

Old:
    doc_ids: ["id1", "id2"]

New:
    docs: [{"id": "id1", "name": "Document 1"}, ...]
"""

import argparse
import sys
import json
import os
from datetime import datetime
from typing import List, Dict
import pymongo


# ────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────

MONGODB_IP = os.environ.get("MONGODB_IP", "localhost")
MONGODB_PORT = os.environ.get("MONGODB_PORT", "27017")

RETRIEVERS_DB = "UnifAI"
SOURCES_DB = "data_sources"

RETRIEVERS_COLLECTION = "resources"
SOURCES_COLLECTION = "sources"

RETRIEVER_TYPE = "docs_dataflow"
CATEGORY = "retrievers"


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def needs_migration(cfg: dict) -> bool:
    # Needs migration if doc_ids field exists (should be renamed to docs)
    if "doc_ids" in cfg:
        return True
    return False


def convert_doc_ids(old: list, docs_map: dict) -> list:
    out = []
    for d in old or []:
        if isinstance(d, str):
            out.append({"id": d, "name": docs_map.get(d, d)})
        elif isinstance(d, dict) and "id" in d:
            if "name" not in d:
                d["name"] = docs_map.get(d["id"], d["id"])
            out.append(d)
    return out


# ────────────────────────────────────────────────────────────────
# Migration
# ────────────────────────────────────────────────────────────────

def migrate(dry_run: bool):
    client = pymongo.MongoClient(f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/")

    retrievers_db = client[RETRIEVERS_DB]
    sources_db = client[SOURCES_DB]

    retrievers = retrievers_db[RETRIEVERS_COLLECTION]
    sources = sources_db[SOURCES_COLLECTION]

    query = {"category": CATEGORY, "type": RETRIEVER_TYPE}
    resources = list(retrievers.find(query))

    print(f"Found {len(resources)} retrievers")

    needed_ids = set()
    for r in resources:
        if needs_migration(r.get("cfg_dict", {})):
            doc_ids = r.get("cfg_dict", {}).get("doc_ids") or []
            for d in doc_ids:
                if isinstance(d, str):
                    needed_ids.add(d)

    docs_map = {}
    if needed_ids:
        print(f"Need to resolve {len(needed_ids)} doc_ids")
        for src in sources.find(
            {"source_id": {"$in": list(needed_ids)}},
            {"source_id": 1, "source_name": 1}
        ):
            docs_map[src["source_id"]] = src.get("source_name", src["source_id"])

    stats = {"checked": 0, "migrated": 0, "skipped": 0}

    for r in resources:
        stats["checked"] += 1
        rid = r.get("rid", r["_id"])
        name = r.get("name", "unnamed")
        cfg = r.get("cfg_dict", {})

        print(f"\n[{rid}] {name}")

        if not needs_migration(cfg):
            print("  Skipped")
            stats["skipped"] += 1
            continue

        old_ids = cfg.get("doc_ids", [])
        new_docs = convert_doc_ids(old_ids, docs_map)

        print(f"  Old doc_ids: {old_ids}")
        print(f"  New docs: {new_docs}")

        if dry_run:
            print("  [DRY RUN] Would update (rename doc_ids -> docs)")
            stats["migrated"] += 1
            continue

        retrievers.update_one(
            {"_id": r["_id"]},
            {
                "$set": {"cfg_dict.docs": new_docs, "updated": datetime.utcnow()},
                "$unset": {"cfg_dict.doc_ids": ""}
            }
        )

        print("  ✓ Migrated")
        stats["migrated"] += 1

    client.close()
    return stats


# ────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    if dry_run:
        print("\n*** DRY RUN MODE ***\n")

    stats = migrate(dry_run)

    print("\nSummary")
    print(stats)

    if dry_run:
        print("\nRun with --apply to commit changes.")


if __name__ == "__main__":
    main()
