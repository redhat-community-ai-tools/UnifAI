#!/usr/bin/env python3
"""
Bidirectional migration between ``user_id`` strings and ``identity`` subdocuments.

  Collection          | Old field(s)                           | New field(s)
  --------------------+----------------------------------------+---------------------------
  blueprints          | user_id                                | identity
  resources           | user_id                                | identity
  workflow_sessions   | user_id  (+ run_context.user_id)       | identity  (+ run_context.identity)
  shares              | sender_user_id, recipient_user_id      | sender_identity, recipient_identity
  templates           | user_id                                | identity  (if present)

Forward (default):
  Wraps each ``user_id`` string into an identity subdocument. If the string matches
  a document in ``teams`` (by ``_id`` or by ``name``), the identity is team-shaped::

      {"type": "team", "id": "<teams._id>", "display_name": "<teams.name>"}

  Otherwise it is a user identity::

      {"type": "user", "id": "<user_id>", "display_name": "<user_id>"}

  Drops old ``user_id``-based indexes so new ``identity.*`` indexes don't conflict.

Reverse (--reverse):
  Extracts ``identity.id`` back into a flat ``user_id`` string, removes the
  ``identity`` subdocument, and drops ``identity.*`` indexes. If that id string
  matches a row in ``teams`` (by ``_id`` or by ``name``), ``user_id`` is set to
  the canonical ``teams._id`` so the flat field stays aligned with team ids.

  **Important:** reverse migration **cannot preserve** whether the owner was a
  ``user`` or a ``team`` — only the id string survives. After you run forward
  again, owners are classified with ``_identity_from_user_id`` (team vs user)
  using ``teams``. The post-forward ``_fix_team_types`` pass still corrects
  remaining ``type: "user"`` rows where heuristics match (see below).

Forward also corrects team-owned documents that were saved with
``identity.type="user"`` instead of ``"team"``:

  * **Blueprints / resources:** ``contributed_by`` / ``metadata.contributed_by``
  * **workflow_sessions:** ``identity.id`` (and ``run_context.identity.id``)
    compared to **``teams._id``** (canonical team id), not display name
  * **shares:** ``sender_identity`` / ``recipient_identity`` when ``*.id`` is a
    known team id

The script is **idempotent** — documents already in the target state are skipped.

Usage:
    # Forward dry run (default)
    python scripts/migrate_user_id_to_identity.py

    # Forward — apply
    python scripts/migrate_user_id_to_identity.py --apply

    # Reverse dry run (back to user_id)
    python scripts/migrate_user_id_to_identity.py --reverse

    # Reverse — apply
    python scripts/migrate_user_id_to_identity.py --reverse --apply

    # Target specific collections
    python scripts/migrate_user_id_to_identity.py --collections blueprints resources

    # Custom MongoDB connection
    MONGODB_IP=10.0.0.5 MONGODB_PORT=27017 python scripts/migrate_user_id_to_identity.py --apply

**Deployment note:** Canonical ``teams`` documents and team APIs live in the
Identity service MongoDB / pod. Run this script against the same database the
Identity deployment uses for ``teams`` and workflow data so team id resolution
stays consistent.
"""

import argparse
import json
import os
import sys

import pymongo

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

MONGODB_IP = os.environ.get("MONGODB_IP", "localhost")
MONGODB_PORT = os.environ.get("MONGODB_PORT", "27017")
DB_NAME = os.environ.get("MONGODB_DB", "UnifAI")

# (user_id_field, identity_field) pairs per collection.
# Forward reads left→right, reverse reads right→left.
COLLECTIONS_CONFIG = {
    "blueprints": {
        "fields": [("user_id", "identity")],
    },
    "resources": {
        "fields": [("user_id", "identity")],
    },
    "workflow_sessions": {
        "fields": [("user_id", "identity")],
        "nested": [("run_context.user_id", "run_context.identity")],
    },
    "shares": {
        "fields": [
            ("sender_user_id", "sender_identity"),
            ("recipient_user_id", "recipient_identity"),
        ],
    },
    "templates": {
        "fields": [("user_id", "identity")],
    },
}

OLD_USER_ID_INDEXES = {
    "resources": ["user_id_1_category_1_type_1_name_1"],
    "workflow_sessions": ["user_id_1_run_id_1"],
}

NEW_IDENTITY_INDEXES = {
    "resources": ["uq_identity_cat_type_name"],
    "workflow_sessions": ["identity.type_1_identity.id_1_run_id_1"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_nested(doc: dict, dot_path: str):
    """Walk a dot-separated path into a nested dict."""
    val = doc
    for part in dot_path.split("."):
        if isinstance(val, dict):
            val = val.get(part, {})
        else:
            return None
    return val


def _load_team_lookups(db) -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """Build lookup maps: team id string / team name -> (canonical_id, display_name).

    ``teams`` uses ``_id`` as the canonical team id (see MongoTeamRepository).
    """
    by_id: dict[str, tuple[str, str]] = {}
    by_name: dict[str, tuple[str, str]] = {}
    if "teams" not in db.list_collection_names():
        return by_id, by_name
    for doc in db["teams"].find({}, {"_id": 1, "name": 1}):
        tid = doc.get("_id")
        name = doc.get("name")
        if tid is None or not name:
            continue
        sid = str(tid)
        name_s = str(name)
        by_id[sid] = (sid, name_s)
        by_name[name_s] = (sid, name_s)
    return by_id, by_name


def _identity_from_user_id(
    user_id: str,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> dict:
    """Map a legacy owner string to an identity; resolve teams via ``teams`` collection."""
    uid = str(user_id)
    if uid in team_by_id:
        tid, tname = team_by_id[uid]
        return {"type": "team", "id": tid, "display_name": tname}
    if uid in team_by_name:
        tid, tname = team_by_name[uid]
        return {"type": "team", "id": tid, "display_name": tname}
    return {"type": "user", "id": uid, "display_name": uid}


def _canonical_user_id_string_for_reverse(
    identity_id: str,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> str:
    """If ``identity.id`` refers to a team (id or legacy name), return ``teams._id``."""
    s = str(identity_id)
    if s in team_by_id:
        return team_by_id[s][0]
    if s in team_by_name:
        return team_by_name[s][0]
    return s


def _accumulate(total: dict, stats: dict) -> None:
    for key in ("found", "updated", "skipped"):
        total[key] += stats[key]
    total["errors"].extend(stats["errors"])


def _drop_indexes(db, index_map: dict, match_keyword: str, dry_run: bool) -> int:
    """Drop named indexes; also scan for any index whose key contains *match_keyword*."""
    dropped = 0
    for coll_name, index_names in index_map.items():
        col = db[coll_name]
        existing = {idx["name"] for idx in col.list_indexes()}

        for idx_name in index_names:
            if idx_name in existing:
                if dry_run:
                    print(f"    [DRY RUN] Would drop index {coll_name}.{idx_name}")
                else:
                    try:
                        col.drop_index(idx_name)
                        print(f"    Dropped index {coll_name}.{idx_name}")
                    except Exception as exc:
                        print(f"    Warning: could not drop {coll_name}.{idx_name}: {exc}")
                dropped += 1

        for idx in col.list_indexes():
            name = idx["name"]
            if name == "_id_" or name in index_names:
                continue
            keys = [k for k, _ in idx.get("key", {}).items()]
            if any(match_keyword in k for k in keys):
                if dry_run:
                    print(f"    [DRY RUN] Would drop legacy index {coll_name}.{name} (keys: {keys})")
                else:
                    try:
                        col.drop_index(name)
                        print(f"    Dropped legacy index {coll_name}.{name}")
                    except Exception as exc:
                        print(f"    Warning: could not drop {coll_name}.{name}: {exc}")
                dropped += 1

    return dropped


# ─────────────────────────────────────────────────────────────────────────────
# Forward: user_id → identity
# ─────────────────────────────────────────────────────────────────────────────

def _forward_collection(
    db,
    coll_name: str,
    field_pairs: list,
    dry_run: bool,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> dict:
    col = db[coll_name]
    stats = {"found": 0, "updated": 0, "skipped": 0, "errors": []}

    for uid_field, id_field in field_pairs:
        query = {uid_field: {"$exists": True}, id_field: {"$exists": False}}
        docs = list(col.find(query, {"_id": 1, uid_field: 1}))

        both_query = {uid_field: {"$exists": True}, id_field: {"$exists": True}}
        both_docs = list(col.find(both_query, {"_id": 1, uid_field: 1}))

        all_docs = docs + both_docs
        stats["found"] += len(all_docs)
        print(f"\n  {coll_name}.{uid_field} -> {id_field}: "
              f"{len(docs)} new + {len(both_docs)} partial = {len(all_docs)} document(s)")

        for doc in all_docs:
            uid = doc.get(uid_field, "")
            if not uid:
                stats["skipped"] += 1
                continue

            identity = _identity_from_user_id(uid, team_by_id, team_by_name)
            if dry_run:
                stats["updated"] += 1
                print(f"    [DRY RUN] _id={doc['_id']}  "
                      f"$set {id_field}={json.dumps(identity)}, $unset {uid_field}")
            else:
                try:
                    res = col.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {id_field: identity}, "$unset": {uid_field: ""}},
                    )
                    stats["updated" if res.modified_count else "skipped"] += 1
                except Exception as exc:
                    stats["errors"].append(f"{doc['_id']}: {exc}")

    return stats


def _forward_nested(
    db,
    coll_name: str,
    nested_pairs: list,
    dry_run: bool,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> dict:
    col = db[coll_name]
    stats = {"found": 0, "updated": 0, "skipped": 0, "errors": []}

    for uid_path, id_path in nested_pairs:
        query = {uid_path: {"$exists": True}, id_path: {"$exists": False}}
        docs = list(col.find(query, {"_id": 1, uid_path: 1}))

        both_query = {uid_path: {"$exists": True}, id_path: {"$exists": True}}
        both_docs = list(col.find(both_query, {"_id": 1, uid_path: 1}))

        all_docs = docs + both_docs
        stats["found"] += len(all_docs)
        print(f"\n  {coll_name} (nested) {uid_path} -> {id_path}: "
              f"{len(docs)} new + {len(both_docs)} partial = {len(all_docs)} document(s)")

        for doc in all_docs:
            uid = _resolve_nested(doc, uid_path)
            if not isinstance(uid, str) or not uid:
                stats["skipped"] += 1
                continue

            identity = _identity_from_user_id(uid, team_by_id, team_by_name)
            if dry_run:
                stats["updated"] += 1
                print(f"    [DRY RUN] _id={doc['_id']}  "
                      f"$set {id_path}={json.dumps(identity)}, $unset {uid_path}")
            else:
                try:
                    res = col.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {id_path: identity}, "$unset": {uid_path: ""}},
                    )
                    stats["updated" if res.modified_count else "skipped"] += 1
                except Exception as exc:
                    stats["errors"].append(f"{doc['_id']}: {exc}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Fix team identity types
# ─────────────────────────────────────────────────────────────────────────────

def _known_team_ids(db) -> list[str]:
    """Return all team ids (``teams`` collection Mongo ``_id`` values)."""
    teams_col = db["teams"]
    out: list[str] = []
    for doc in teams_col.find({}, {"_id": 1}):
        tid = doc.get("_id")
        if tid is not None:
            out.append(str(tid))
    return out


def _fix_team_types(db, dry_run: bool) -> dict:
    """Correct identity.type='user' → 'team' for team-owned documents."""
    stats = {
        "blueprints": 0,
        "resources": 0,
        "sessions": 0,
        "sessions_run_context": 0,
        "shares_sender": 0,
        "shares_recipient": 0,
    }

    team_id_list = _known_team_ids(db)
    if not team_id_list:
        print("\n  [teams] no team documents found — session/share team-id fixes are skipped")

    # Blueprints: contributed_by marker means it was shared to a team
    bp_col = db["blueprints"]
    bp_query = {"metadata.contributed_by": {"$exists": True}, "identity.type": "user"}
    bp_docs = list(bp_col.find(bp_query, {"_id": 1, "blueprint_id": 1, "identity": 1,
                                           "metadata.contributed_by": 1}))
    print(f"\n  blueprints: {len(bp_docs)} team-owned doc(s) with wrong identity.type")
    for doc in bp_docs:
        if dry_run:
            bp_id = doc.get("blueprint_id", doc["_id"])
            owner = doc.get("identity", {}).get("id", "?")
            print(f"    [DRY RUN] blueprint_id={bp_id}  owner={owner}  → identity.type=team")
        else:
            bp_col.update_one({"_id": doc["_id"]}, {"$set": {"identity.type": "team"}})
        stats["blueprints"] += 1

    # Resources: contributed_by marker
    res_col = db["resources"]
    res_query = {"contributed_by": {"$exists": True, "$ne": None}, "identity.type": "user"}
    res_docs = list(res_col.find(res_query, {"_id": 1, "identity": 1, "name": 1,
                                              "contributed_by": 1}))
    print(f"\n  resources: {len(res_docs)} team-owned doc(s) with wrong identity.type")
    for doc in res_docs:
        if dry_run:
            name = doc.get("name", "?")
            owner = doc.get("identity", {}).get("id", "?")
            print(f"    [DRY RUN] rid={doc['_id']}  name={name}  owner={owner}  → identity.type=team")
        else:
            res_col.update_one({"_id": doc["_id"]}, {"$set": {"identity.type": "team"}})
        stats["resources"] += 1

    # Sessions: identity.id must match a real team id (teams._id).  After a
    # reverse→forward round-trip, team-owned rows become type=user with id still
    # equal to the team uuid — the old name-only check missed almost all of them.
    if team_id_list:
        sess_col = db["workflow_sessions"]
        sess_query = {"identity.id": {"$in": team_id_list}, "identity.type": "user"}
        sess_docs = list(sess_col.find(sess_query, {"_id": 1, "run_id": 1, "identity": 1}))
        print(f"\n  sessions (top-level identity): {len(sess_docs)} doc(s) "
              f"with identity.id ∈ teams._id but identity.type=user")
        for doc in sess_docs:
            if dry_run:
                run_id = doc.get("run_id", doc["_id"])
                owner = doc.get("identity", {}).get("id", "?")
                print(f"    [DRY RUN] run_id={run_id}  owner={owner}  → identity.type=team")
            else:
                sess_col.update_one({"_id": doc["_id"]}, {"$set": {"identity.type": "team"}})
            stats["sessions"] += 1

        rc_query = {
            "run_context.identity.id": {"$in": team_id_list},
            "run_context.identity.type": "user",
        }
        rc_docs = list(sess_col.find(rc_query, {"_id": 1, "run_id": 1, "run_context.identity": 1}))
        print(f"\n  sessions (run_context.identity): {len(rc_docs)} doc(s) to fix")
        for doc in rc_docs:
            if dry_run:
                run_id = doc.get("run_id", doc["_id"])
                owner = _resolve_nested(doc, "run_context.identity.id") or "?"
                print(f"    [DRY RUN] run_id={run_id}  run_context.identity.id={owner}  → type=team")
            else:
                sess_col.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"run_context.identity.type": "team"}},
                )
            stats["sessions_run_context"] += 1

        # Shares: sender or recipient may be a team; reverse+forward loses type.
        if "shares" in db.list_collection_names():
            sh_col = db["shares"]
            snd_query = {
                "sender_identity.id": {"$in": team_id_list},
                "sender_identity.type": "user",
            }
            snd_docs = list(sh_col.find(snd_query, {"_id": 1, "sender_identity": 1}))
            print(f"\n  shares (sender_identity): {len(snd_docs)} doc(s) to fix")
            for doc in snd_docs:
                if dry_run:
                    print(f"    [DRY RUN] _id={doc['_id']}  → sender_identity.type=team")
                else:
                    sh_col.update_one({"_id": doc["_id"]}, {"$set": {"sender_identity.type": "team"}})
                stats["shares_sender"] += 1

            rcv_query = {
                "recipient_identity.id": {"$in": team_id_list},
                "recipient_identity.type": "user",
            }
            rcv_docs = list(sh_col.find(rcv_query, {"_id": 1, "recipient_identity": 1}))
            print(f"\n  shares (recipient_identity): {len(rcv_docs)} doc(s) to fix")
            for doc in rcv_docs:
                if dry_run:
                    print(f"    [DRY RUN] _id={doc['_id']}  → recipient_identity.type=team")
                else:
                    sh_col.update_one({"_id": doc["_id"]}, {"$set": {"recipient_identity.type": "team"}})
                stats["shares_recipient"] += 1

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Reverse: identity → user_id
# ─────────────────────────────────────────────────────────────────────────────

def _reverse_collection(
    db,
    coll_name: str,
    field_pairs: list,
    dry_run: bool,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> dict:
    col = db[coll_name]
    stats = {"found": 0, "updated": 0, "skipped": 0, "errors": []}

    for uid_field, id_field in field_pairs:
        query = {id_field: {"$exists": True}, uid_field: {"$exists": False}}
        docs = list(col.find(query, {"_id": 1, id_field: 1}))

        both_query = {id_field: {"$exists": True}, uid_field: {"$exists": True}}
        both_docs = list(col.find(both_query, {"_id": 1, id_field: 1}))

        all_docs = docs + both_docs
        stats["found"] += len(all_docs)
        print(f"\n  {coll_name}.{id_field} -> {uid_field}: "
              f"{len(docs)} new + {len(both_docs)} partial = {len(all_docs)} document(s)")

        for doc in all_docs:
            identity = doc.get(id_field)
            if not isinstance(identity, dict):
                stats["skipped"] += 1
                continue
            uid = identity.get("id", "")
            if not uid:
                stats["skipped"] += 1
                continue
            uid = _canonical_user_id_string_for_reverse(uid, team_by_id, team_by_name)

            if dry_run:
                stats["updated"] += 1
                print(f"    [DRY RUN] _id={doc['_id']}  "
                      f"$set {uid_field}={uid!r}, $unset {id_field}")
            else:
                try:
                    res = col.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {uid_field: uid}, "$unset": {id_field: ""}},
                    )
                    stats["updated" if res.modified_count else "skipped"] += 1
                except Exception as exc:
                    stats["errors"].append(f"{doc['_id']}: {exc}")

    return stats


def _reverse_nested(
    db,
    coll_name: str,
    nested_pairs: list,
    dry_run: bool,
    team_by_id: dict[str, tuple[str, str]],
    team_by_name: dict[str, tuple[str, str]],
) -> dict:
    col = db[coll_name]
    stats = {"found": 0, "updated": 0, "skipped": 0, "errors": []}

    for uid_path, id_path in nested_pairs:
        query = {id_path: {"$exists": True}, uid_path: {"$exists": False}}
        docs = list(col.find(query, {"_id": 1, id_path: 1}))
        stats["found"] += len(docs)
        print(f"\n  {coll_name} (nested) {id_path} -> {uid_path}: {len(docs)} document(s)")

        for doc in docs:
            identity = _resolve_nested(doc, id_path)
            uid = identity.get("id", "") if isinstance(identity, dict) else ""
            if not uid:
                stats["skipped"] += 1
                continue
            uid = _canonical_user_id_string_for_reverse(uid, team_by_id, team_by_name)

            if dry_run:
                stats["updated"] += 1
                print(f"    [DRY RUN] _id={doc['_id']}  "
                      f"$set {uid_path}={uid!r}, $unset {id_path}")
            else:
                try:
                    res = col.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {uid_path: uid}, "$unset": {id_path: ""}},
                    )
                    stats["updated" if res.modified_count else "skipped"] += 1
                except Exception as exc:
                    stats["errors"].append(f"{doc['_id']}: {exc}")

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migrate between user_id and identity schema (bidirectional, idempotent).",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Reverse: convert identity subdocuments back to user_id strings",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "--collections", "-c",
        nargs="*",
        default=None,
        help="Limit migration to these collections (default: all)",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip index cleanup",
    )
    args = parser.parse_args()

    dry_run = not args.apply
    reverse = args.reverse
    targets = args.collections or list(COLLECTIONS_CONFIG.keys())
    direction = "REVERSE (identity → user_id)" if reverse else "FORWARD (user_id → identity)"

    mongo_uri = f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/"
    print(f"Connecting to MongoDB: {mongo_uri}")
    print(f"Database: {DB_NAME}")
    print(f"Direction: {direction}")
    if reverse:
        print(
            "\nNote: reverse drops identity — only one owner string is kept as user_id.\n"
            "If identity.id matched a team (by id or name), user_id is the canonical teams._id.\n"
            "After forward migration, team owners get type=id+display_name from teams.",
        )

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE — no changes will be made")
        print("Use --apply to actually apply changes")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print(f"APPLYING CHANGES — {direction}")
        print("=" * 60)

    client = pymongo.MongoClient(mongo_uri)
    db = client[DB_NAME]

    total_stats = {"found": 0, "updated": 0, "skipped": 0, "errors": []}

    # Index cleanup BEFORE data migration (avoids null unique-key violations)
    if not args.skip_indexes:
        print(f"\n{'=' * 60}")
        print("INDEX CLEANUP")
        print(f"{'=' * 60}")
        if reverse:
            dropped = _drop_indexes(db, NEW_IDENTITY_INDEXES, "identity", dry_run)
        else:
            dropped = _drop_indexes(db, OLD_USER_ID_INDEXES, "user_id", dry_run)
        if dropped == 0:
            print("  No stale indexes found — nothing to clean up.")

    team_by_id, team_by_name = _load_team_lookups(db)
    n_teams = len(team_by_id)
    if n_teams:
        print(
            f"\nLoaded {n_teams} team(s) for "
            f"{'reverse user_id canonicalization and ' if reverse else ''}"
            f"forward owner → identity resolution (id + name lookup).",
        )

    for coll_name in targets:
        cfg = COLLECTIONS_CONFIG.get(coll_name)
        if not cfg:
            print(f"\n  [SKIP] Unknown collection: {coll_name}")
            continue

        print(f"\n{'=' * 60}")
        print(f"COLLECTION: {coll_name}")
        print(f"{'=' * 60}")

        if reverse:
            _accumulate(
                total_stats,
                _reverse_collection(
                    db, coll_name, cfg["fields"], dry_run, team_by_id, team_by_name
                ),
            )
        else:
            _accumulate(
                total_stats,
                _forward_collection(
                    db, coll_name, cfg["fields"], dry_run, team_by_id, team_by_name
                ),
            )

        nested = cfg.get("nested", [])
        if nested:
            if reverse:
                _accumulate(
                    total_stats,
                    _reverse_nested(
                        db, coll_name, nested, dry_run, team_by_id, team_by_name
                    ),
                )
            else:
                _accumulate(
                    total_stats,
                    _forward_nested(
                        db, coll_name, nested, dry_run, team_by_id, team_by_name
                    ),
                )

    # On forward migration, fix team identity types
    if not reverse:
        print(f"\n{'=' * 60}")
        print("FIX TEAM IDENTITY TYPES")
        print(f"{'=' * 60}")
        fix_stats = _fix_team_types(db, dry_run)
        verb = "Would fix" if dry_run else "Fixed"
        print(
            f"\n  {verb}: {fix_stats['blueprints']} blueprints, "
            f"{fix_stats['resources']} resources, "
            f"{fix_stats['sessions']} sessions, "
            f"{fix_stats['sessions_run_context']} session run_context, "
            f"{fix_stats['shares_sender']} share senders, "
            f"{fix_stats['shares_recipient']} share recipients",
        )

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Direction:             {direction}")
    print(f"  Collections processed: {len(targets)}")
    print(f"  Documents found:       {total_stats['found']}")
    print(f"  {'Would update' if dry_run else 'Updated'}:          {total_stats['updated']}")
    print(f"  Skipped:               {total_stats['skipped']}")
    if total_stats["errors"]:
        print(f"  Errors:                {len(total_stats['errors'])}")
        for err in total_stats["errors"]:
            print(f"    - {err}")

    if dry_run:
        print(f"\nThis was a DRY RUN. Use --apply to make changes.")
    else:
        label = "Reverse migration" if reverse else "Migration"
        print(f"\n{label} complete!")

    client.close()
    return 0 if not total_stats["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
