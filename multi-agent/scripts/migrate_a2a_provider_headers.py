#!/usr/bin/env python3
"""
Migrate legacy A2A provider config field ``headers`` → ``additional_headers``.

On GENIE-1692, ``A2AProviderConfig.headers`` was renamed to ``additional_headers``
with ``extra=forbid``. Any saved Provider resources of type ``a2a_agent`` that
still store ``cfg_dict.headers`` will fail Pydantic validation on load.

This script is idempotent. Prefer ``--dry-run`` first.

Usage:
  export MONGODB_IP=127.0.0.1
  export MONGODB_PORT=27017
  export MONGO_DB=UnifAI
  python scripts/migrate_a2a_provider_headers.py --dry-run
  python scripts/migrate_a2a_provider_headers.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo import MongoClient

MONGODB_IP = os.environ.get("MONGODB_IP", "127.0.0.1")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGO_DB = os.environ.get("MONGO_DB", "UnifAI")
COLL_NAME = os.environ.get("RESOURCES_COLL", "resources")

# Provider-category A2A element type (see providers/a2a_client/identifiers.py).
_FILTER = {
    "category": "provider",
    "type": "a2a_agent",
    "cfg_dict.headers": {"$exists": True},
}


def _merge_headers(
    existing_additional: Optional[Any],
    legacy_headers: Optional[Any],
) -> Dict[str, Any]:
    """Prefer explicit additional_headers keys over legacy headers on conflict."""
    merged: Dict[str, Any] = {}
    if isinstance(legacy_headers, dict):
        merged.update({str(k): v for k, v in legacy_headers.items()})
    if isinstance(existing_additional, dict):
        merged.update({str(k): v for k, v in existing_additional.items()})
    return merged


def migrate(*, dry_run: bool) -> int:
    client = MongoClient(f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/")
    coll = client[MONGO_DB][COLL_NAME]

    docs = list(coll.find(_FILTER, {"_id": 1, "name": 1, "cfg_dict": 1}))
    print(f"Found {len(docs)} A2A provider resource(s) with cfg_dict.headers")

    updated = 0
    for doc in docs:
        rid = doc["_id"]
        cfg = dict(doc.get("cfg_dict") or {})
        legacy = cfg.get("headers")
        additional = cfg.get("additional_headers")
        merged = _merge_headers(additional, legacy)

        print(
            f"  - {rid} name={doc.get('name')!r} "
            f"legacy_keys={list(legacy) if isinstance(legacy, dict) else type(legacy)}"
        )

        if dry_run:
            continue

        coll.update_one(
            {"_id": rid},
            {
                "$set": {
                    "cfg_dict.additional_headers": merged,
                    "updated": datetime.now(timezone.utc),
                },
                "$unset": {"cfg_dict.headers": ""},
            },
        )
        updated += 1

    if dry_run:
        print("Dry run only — no documents modified.")
    else:
        print(f"Migrated {updated} document(s).")
    return 0 if docs or dry_run else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching docs without writing",
    )
    args = parser.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
