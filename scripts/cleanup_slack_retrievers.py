#!/usr/bin/env python3
"""
Find and clean up Slack retrievers and their associated blueprints.

Usage:
    # Dry run - list all slack retrievers and blueprints using them
    python cleanup_slack_retrievers.py
    
    # Apply changes - delete slack retrievers and blueprints
    python cleanup_slack_retrievers.py --apply

Flow:
    1. Find all slack retrievers (category: 'retrievers', type: 'slack')
    2. Display owner names for each retriever
    3. Find blueprints that reference these retrievers
    4. With --apply: delete slack retrievers and associated blueprints
"""

import os
import argparse
from datetime import datetime
from typing import List, Dict, Any, Set
import pymongo


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

MONGODB_IP = os.environ.get("MONGODB_IP", "localhost")
MONGODB_PORT = os.environ.get("MONGODB_PORT", "27017")
DB_NAME = "UnifAI"

RESOURCES_COLLECTION = "resources"
BLUEPRINTS_COLLECTION = "blueprints"

# Query for slack retrievers
SLACK_RETRIEVER_QUERY = {"category": "retrievers", "type": "slack"}


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def find_slack_retrievers(db) -> List[Dict[str, Any]]:
    """Find all slack retrievers in the resources collection."""
    collection = db[RESOURCES_COLLECTION]
    return list(collection.find(SLACK_RETRIEVER_QUERY))


def find_blueprints_using_retriever(db, rid: str) -> List[Dict[str, Any]]:
    """Find blueprints that reference a specific retriever by rid."""
    collection = db[BLUEPRINTS_COLLECTION]
    
    # Blueprints store references in rid_refs array
    query = {"rid_refs": rid}
    
    return list(collection.find(query))


def find_blueprints_with_inline_slack(db) -> List[Dict[str, Any]]:
    """Find blueprints that have inline slack retrievers (not via rid_refs)."""
    collection = db[BLUEPRINTS_COLLECTION]
    
    # Check for inline slack retrievers in spec_dict.retrievers
    query = {"spec_dict.retrievers.config.type": "slack"}
    
    return list(collection.find(query))


def delete_retriever(db, rid: str, dry_run: bool = True) -> bool:
    """Delete a retriever by rid."""
    if dry_run:
        return True
    
    collection = db[RESOURCES_COLLECTION]
    result = collection.delete_one({"_id": rid})
    return result.deleted_count > 0


def delete_blueprint(db, blueprint_id: str, dry_run: bool = True) -> bool:
    """Delete a blueprint by blueprint_id."""
    if dry_run:
        return True
    
    collection = db[BLUEPRINTS_COLLECTION]
    result = collection.delete_one({"blueprint_id": blueprint_id})
    return result.deleted_count > 0


# ─────────────────────────────────────────────────────────────────────────────
# Main Logic
# ─────────────────────────────────────────────────────────────────────────────

def display_slack_retrievers(retrievers: List[Dict[str, Any]]) -> None:
    """Display information about slack retrievers."""
    print(f"\n{'='*60}")
    print("SLACK RETRIEVERS FOUND")
    print(f"{'='*60}")
    print(f"Total: {len(retrievers)}")
    
    if not retrievers:
        print("  No slack retrievers found.")
        return
    
    # Group by owner
    owners: Dict[str, List[Dict]] = {}
    for r in retrievers:
        owner = r.get("user_id", "unknown")
        if owner not in owners:
            owners[owner] = []
        owners[owner].append(r)
    
    print(f"\nOwners: {len(owners)}")
    for owner, items in sorted(owners.items()):
        print(f"\n  Owner: {owner}")
        print(f"  {'─'*50}")
        for item in items:
            rid = item.get("rid", item.get("_id", "unknown"))
            name = item.get("name", "unnamed")
            created = item.get("created", "unknown")
            cfg = item.get("cfg_dict", {})
            print(f"    • [{rid}] {name}")
            print(f"      Created: {created}")
            print(f"      Config: {cfg}")


def display_affected_blueprints(blueprints: List[Dict[str, Any]], 
                                 retriever_rids: Set[str]) -> None:
    """Display information about blueprints using slack retrievers."""
    print(f"\n{'='*60}")
    print("BLUEPRINTS USING SLACK RETRIEVERS")
    print(f"{'='*60}")
    print(f"Total: {len(blueprints)}")
    
    if not blueprints:
        print("  No blueprints using slack retrievers found.")
        return
    
    # Group by owner
    owners: Dict[str, List[Dict]] = {}
    for bp in blueprints:
        owner = bp.get("user_id", "unknown")
        if owner not in owners:
            owners[owner] = []
        owners[owner].append(bp)
    
    print(f"\nOwners: {len(owners)}")
    for owner, items in sorted(owners.items()):
        print(f"\n  Owner: {owner}")
        print(f"  {'─'*50}")
        for bp in items:
            bp_id = bp.get("blueprint_id", "unknown")
            spec = bp.get("spec_dict", {})
            name = spec.get("name", "unnamed")
            updated = bp.get("updated_at", "unknown")
            
            # Find which slack retrievers this blueprint uses
            rid_refs = bp.get("rid_refs", [])
            used_slack_refs = [r for r in rid_refs if r in retriever_rids]
            
            print(f"    • [{bp_id}] {name}")
            print(f"      Updated: {updated}")
            if used_slack_refs:
                print(f"      Uses retrievers: {used_slack_refs}")


def cleanup(db, dry_run: bool = True) -> Dict[str, Any]:
    """
    Main cleanup function.
    
    Args:
        db: MongoDB database
        dry_run: If True, only show what would be deleted
    
    Returns:
        Stats dict with counts
    """
    stats = {
        "retrievers_found": 0,
        "retrievers_deleted": 0,
        "blueprints_found": 0,
        "blueprints_deleted": 0,
        "errors": []
    }
    
    # Step 1: Find all slack retrievers
    print("\n🔍 Searching for slack retrievers...")
    retrievers = find_slack_retrievers(db)
    stats["retrievers_found"] = len(retrievers)
    
    display_slack_retrievers(retrievers)
    
    if not retrievers:
        return stats
    
    # Get all retriever rids
    retriever_rids = set()
    for r in retrievers:
        rid = r.get("rid", r.get("_id"))
        if rid:
            retriever_rids.add(rid)
    
    # Step 2: Find blueprints using these retrievers
    print("\n🔍 Searching for blueprints using slack retrievers...")
    
    all_blueprints: Dict[str, Dict] = {}  # blueprint_id -> blueprint doc
    
    # Find via rid_refs
    for rid in retriever_rids:
        bps = find_blueprints_using_retriever(db, rid)
        for bp in bps:
            bp_id = bp.get("blueprint_id")
            if bp_id and bp_id not in all_blueprints:
                all_blueprints[bp_id] = bp
    
    # Also find blueprints with inline slack retrievers
    inline_bps = find_blueprints_with_inline_slack(db)
    for bp in inline_bps:
        bp_id = bp.get("blueprint_id")
        if bp_id and bp_id not in all_blueprints:
            all_blueprints[bp_id] = bp
    
    blueprints = list(all_blueprints.values())
    stats["blueprints_found"] = len(blueprints)
    
    display_affected_blueprints(blueprints, retriever_rids)
    
    # Step 3: Delete if not dry run
    if not dry_run:
        print(f"\n{'='*60}")
        print("DELETING RESOURCES")
        print(f"{'='*60}")
        
        # Delete blueprints first (they reference retrievers)
        print("\n📦 Deleting blueprints...")
        for bp in blueprints:
            bp_id = bp.get("blueprint_id")
            bp_name = bp.get("spec_dict", {}).get("name", "unnamed")
            try:
                if delete_blueprint(db, bp_id, dry_run=False):
                    stats["blueprints_deleted"] += 1
                    print(f"  ✓ Deleted blueprint: [{bp_id}] {bp_name}")
                else:
                    print(f"  ✗ Failed to delete blueprint: [{bp_id}] {bp_name}")
            except Exception as e:
                stats["errors"].append(f"Blueprint {bp_id}: {str(e)}")
                print(f"  ✗ Error deleting blueprint [{bp_id}]: {e}")
        
        # Then delete retrievers
        print("\n🔧 Deleting slack retrievers...")
        for r in retrievers:
            rid = r.get("rid", r.get("_id"))
            name = r.get("name", "unnamed")
            try:
                if delete_retriever(db, rid, dry_run=False):
                    stats["retrievers_deleted"] += 1
                    print(f"  ✓ Deleted retriever: [{rid}] {name}")
                else:
                    print(f"  ✗ Failed to delete retriever: [{rid}] {name}")
            except Exception as e:
                stats["errors"].append(f"Retriever {rid}: {str(e)}")
                print(f"  ✗ Error deleting retriever [{rid}]: {e}")
    
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find and clean up Slack retrievers and associated blueprints"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes - delete slack retrievers and blueprints (default is dry-run)"
    )
    parser.add_argument(
        "--mongodb-ip",
        default=MONGODB_IP,
        help=f"MongoDB IP address (default: {MONGODB_IP})"
    )
    parser.add_argument(
        "--mongodb-port",
        default=MONGODB_PORT,
        help=f"MongoDB port (default: {MONGODB_PORT})"
    )
    args = parser.parse_args()
    
    dry_run = not args.apply
    
    # Connect to MongoDB
    mongo_uri = f"mongodb://{args.mongodb_ip}:{args.mongodb_port}/"
    print(f"Connecting to MongoDB: {mongo_uri}")
    print(f"Database: {DB_NAME}")
    
    client = pymongo.MongoClient(mongo_uri)
    db = client[DB_NAME]
    
    if dry_run:
        print("\n" + "="*60)
        print("🔍 DRY RUN MODE - No changes will be made")
        print("   Use --apply to actually delete resources")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("⚠️  APPLYING CHANGES - Resources will be deleted!")
        print("="*60)
    
    # Run cleanup
    stats = cleanup(db, dry_run)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Slack retrievers found: {stats['retrievers_found']}")
    print(f"  Blueprints using slack: {stats['blueprints_found']}")
    
    if not dry_run:
        print(f"\n  Retrievers deleted: {stats['retrievers_deleted']}")
        print(f"  Blueprints deleted: {stats['blueprints_deleted']}")
    
    if stats['errors']:
        print(f"\n  ❌ Errors: {len(stats['errors'])}")
        for err in stats['errors']:
            print(f"    - {err}")
    
    if dry_run:
        print(f"\n📌 This was a DRY RUN. Use --apply to delete resources.")
    else:
        print(f"\n✅ Cleanup complete!")
    
    client.close()


if __name__ == "__main__":
    main()

