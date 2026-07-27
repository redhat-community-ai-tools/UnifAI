#!/usr/bin/env python3
"""
One-time script: seed pre-defined templates into MongoDB.

Reads YAML fixtures from run/fixtures/templates/ and inserts any that
don't already exist (including soft-deleted ones, so admin deletions
are preserved).

Usage:
  export MONGODB_IP=mongodb      # default 127.0.0.1
  export MONGODB_PORT=27017
  export MONGO_DB=UnifAI
  python scripts/seed_templates.py
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MULTI_AGENT_ROOT = os.path.dirname(SCRIPT_DIR)
if MULTI_AGENT_ROOT not in sys.path:
    sys.path.insert(0, MULTI_AGENT_ROOT)

LIB_DIR = os.path.join(MULTI_AGENT_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from outbound.mongo.template_repository import MongoTemplateRepository
from run.fixtures.seeder import seed_templates

MONGO_DB = os.environ.get("MONGO_DB", "UnifAI")
TEMPLATES_COLL = os.environ.get("TEMPLATES_COLL", "templates")


def main() -> int:
    mongodb_ip = os.environ.get("MONGODB_IP", "127.0.0.1")
    mongodb_port = os.environ.get("MONGODB_PORT", "27017")
    print(f"Connecting to MongoDB at {mongodb_ip}:{mongodb_port}, db={MONGO_DB}")

    repo = MongoTemplateRepository(db_name=MONGO_DB, coll_name=TEMPLATES_COLL)

    inserted = seed_templates(repo)
    print(f"Done — {inserted} template(s) inserted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
