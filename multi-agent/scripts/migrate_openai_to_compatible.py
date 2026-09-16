#!/usr/bin/env python3
"""
Migrate legacy ``openai`` LLM resources after the provider split.

Before this branch, the single ``openai`` provider used the Chat Completions
API (``/v1/chat/completions``).  The provider has now been split:

- ``openai``            — OpenAI Responses API only (GPT-5+, o-series).
                          Does **not** support ``temperature``.
- ``openai_compatible`` — Chat Completions API (vLLM, Ollama, older OpenAI
                          models such as GPT-4 / GPT-3.5).

This script performs two operations on every saved ``type: "openai"`` LLM
resource:

1. **Type migration** — If the ``model_name`` does NOT match a known
   Responses-API prefix (``gpt-5``, ``o1``, ``o3``, ``o4``), the resource is
   migrated to ``type: "openai_compatible"`` so it continues to work against
   the Chat Completions endpoint.  Resources with a Responses-API model are
   left as ``type: "openai"``.

2. **Temperature removal** — Resources that stay as ``type: "openai"`` have
   the ``cfg_dict.temperature`` field removed because the Responses API does
   not accept it.

This script is idempotent.  Prefer ``--dry-run`` first.

Usage::

    export MONGODB_IP=127.0.0.1
    export MONGODB_PORT=27017
    export MONGO_DB=UnifAI

    # Preview what will be changed
    python scripts/migrate_openai_to_compatible.py --dry-run

    # Apply
    python scripts/migrate_openai_to_compatible.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from pymongo import MongoClient

MONGODB_IP = os.environ.get("MONGODB_IP", "127.0.0.1")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGO_DB = os.environ.get("MONGO_DB", "UnifAI")
COLL_NAME = os.environ.get("RESOURCES_COLL", "resources")

# Model-name prefixes that require the Responses API.
# Resources whose model_name starts with any of these stay as type="openai".
# All others are migrated to type="openai_compatible".
_RESPONSES_API_PREFIXES = ("gpt-5", "o1", "o3", "o4")


def _is_responses_api_model(model_name: str) -> bool:
    return any(model_name.startswith(p) for p in _RESPONSES_API_PREFIXES)


def migrate(*, dry_run: bool) -> int:
    client = MongoClient(f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/")
    coll = client[MONGO_DB][COLL_NAME]

    docs = list(coll.find({"category": "llms", "type": "openai"}, {"_id": 1, "name": 1, "cfg_dict": 1}))
    print(f"Found {len(docs)} LLM resource(s) with type='openai'\n")

    if not docs:
        print("Nothing to migrate.")
        return 0

    to_compatible: list = []   # need type change (and temperature drop)
    keep_openai: list = []     # stay as openai, but drop temperature

    for doc in docs:
        cfg = doc.get("cfg_dict") or {}
        model = cfg.get("model_name", "")
        has_temp = "temperature" in cfg
        if _is_responses_api_model(model):
            keep_openai.append((doc, has_temp))
        else:
            to_compatible.append((doc, has_temp))

    print(f"→ Migrate to 'openai_compatible': {len(to_compatible)} resource(s)")
    for doc, has_temp in to_compatible:
        cfg = doc.get("cfg_dict") or {}
        print(
            f"   id={doc['_id']}  name={doc.get('name')!r}"
            f"  model={cfg.get('model_name', '?')!r}"
            f"  base_url={cfg.get('base_url', '?')!r}"
            f"  temperature={'yes' if has_temp else 'no'}"
        )

    print(f"\n→ Keep as 'openai' (remove temperature): {len(keep_openai)} resource(s)")
    for doc, has_temp in keep_openai:
        cfg = doc.get("cfg_dict") or {}
        print(
            f"   id={doc['_id']}  name={doc.get('name')!r}"
            f"  model={cfg.get('model_name', '?')!r}"
            f"  temperature={'yes — will be removed' if has_temp else 'not set'}"
        )

    if dry_run:
        print("\nDry run only — no documents modified.")
        return 0

    now = datetime.now(timezone.utc)

    # 1. Migrate Chat Completions resources → openai_compatible
    if to_compatible:
        ids = [doc["_id"] for doc, _ in to_compatible]
        coll.update_many(
            {"_id": {"$in": ids}},
            {
                "$set": {"type": "openai_compatible", "updated": now},
                "$unset": {"cfg_dict.temperature": ""},
            },
        )
        print(f"\nMigrated {len(ids)} resource(s) to 'openai_compatible' (temperature removed).")

    # 2. Keep Responses-API resources as openai — only remove temperature
    if keep_openai:
        ids = [doc["_id"] for doc, _ in keep_openai]
        coll.update_many(
            {"_id": {"$in": ids}},
            {
                "$set": {"updated": now},
                "$unset": {"cfg_dict.temperature": ""},
            },
        )
        print(f"Cleaned temperature from {len(ids)} 'openai' resource(s).")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching documents without writing any changes.",
    )
    args = parser.parse_args()
    return migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
