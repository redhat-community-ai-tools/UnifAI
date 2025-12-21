#!/usr/bin/env python3
"""
Migrate 'docs' retrievers to 'docs_dataflow' format.

Usage:
    # Dry run on resources collection (default query)
    python migrate_docs_retriever.py
    
    # Dry run with custom query
    python migrate_docs_retriever.py --query '{"category": "retrievers", "type": "docs"}'
    
    # Specify collection
    python migrate_docs_retriever.py --collection resources --query '{"type": "docs"}'
    
    # Apply changes
    python migrate_docs_retriever.py --apply
"""

import os
import json
import argparse
from datetime import datetime
import pymongo


# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

MONGODB_IP = os.environ.get("MONGODB_IP", "localhost")
MONGODB_PORT = os.environ.get("MONGODB_PORT", "27017")
DB_NAME = "UnifAI" # Can be changed if needed

# Default query for docs retrievers
DEFAULT_QUERY = {"category": "retrievers", "type": "docs"}
DEFAULT_COLLECTION = "resources"


# ─────────────────────────────────────────────────────────────────────────────
# Transform Function
# ─────────────────────────────────────────────────────────────────────────────

def transform_cfg_dict(old_cfg: dict) -> dict:
    """
    Transform old 'docs' cfg_dict to new 'docs_dataflow' format.
    
    Old format:
        type: 'docs'
        api_url: 'http://...'
        top_k_results: 3
        threshold: 0.3
    
    New format:
        type: 'docs_dataflow'
        top_k_results: 3
        threshold: 0.3
        timeout: 30
        doc_ids: null
        tags: null
    """
    return {
        "type": "docs_dataflow",
        "top_k_results": old_cfg.get("top_k_results", 3),
        "threshold": old_cfg.get("threshold", 0.3),
        "timeout": old_cfg.get("timeout", 30.0),
        "doc_ids": old_cfg.get("doc_ids", None),
        "tags": old_cfg.get("tags", None),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Migration
# ─────────────────────────────────────────────────────────────────────────────

def migrate(db, collection_name: str, query: dict, dry_run: bool = True) -> dict:
    """
    Find and update documents matching the query.
    
    Args:
        db: MongoDB database
        collection_name: Name of collection to update
        query: MongoDB query filter
        dry_run: If True, only show what would change
    
    Returns:
        Stats dict with counts
    """
    collection = db[collection_name]
    
    # Find matching documents
    docs = list(collection.find(query))
    
    stats = {"found": len(docs), "updated": 0, "errors": []}
    
    print(f"\n{'='*60}")
    print(f"COLLECTION: {collection_name}")
    print(f"QUERY: {json.dumps(query)}")
    print(f"{'='*60}")
    print(f"Found {len(docs)} document(s)")
    
    for doc in docs:
        rid = doc.get("rid", doc.get("_id"))
        name = doc.get("name", "unnamed")
        user_id = doc.get("user_id", "unknown")
        
        print(f"\n  [{rid}] {name} (user: {user_id})")
        print(f"    Old cfg_dict: {doc.get('cfg_dict', {})}")
        
        try:
            # Transform cfg_dict
            new_cfg = transform_cfg_dict(doc.get("cfg_dict", {}))
            print(f"    New cfg_dict: {new_cfg}")
            
            if not dry_run:
                # Update both top-level type and cfg_dict
                result = collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "type": "docs_dataflow",
                            "cfg_dict": new_cfg,
                            "updated": datetime.utcnow()
                        }
                    }
                )
                if result.modified_count > 0:
                    stats["updated"] += 1
                    print(f"    ✓ Updated")
                else:
                    print(f"    ✗ No changes made")
            else:
                stats["updated"] += 1
                print(f"    [DRY RUN] Would update")
                
        except Exception as e:
            stats["errors"].append(f"{rid}: {str(e)}")
            print(f"    ✗ Error: {e}")
    
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Migrate 'docs' retrievers to 'docs_dataflow' format"
    )
    parser.add_argument(
        "--collection", "-c",
        default=DEFAULT_COLLECTION,
        help=f"Collection name (default: {DEFAULT_COLLECTION})"
    )
    parser.add_argument(
        "--query", "-q",
        default=None,
        help=f"MongoDB query as JSON string (default: {json.dumps(DEFAULT_QUERY)})"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)"
    )
    args = parser.parse_args()
    
    # Parse query
    if args.query:
        try:
            query = json.loads(args.query)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON query: {e}")
            return
    else:
        query = DEFAULT_QUERY
    
    dry_run = not args.apply
    
    # Connect to MongoDB
    mongo_uri = f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/"
    print(f"Connecting to MongoDB: {mongo_uri}")
    print(f"Database: {DB_NAME}")
    
    client = pymongo.MongoClient(mongo_uri)
    db = client[DB_NAME]
    
    if dry_run:
        print("\n" + "="*60)
        print("DRY RUN MODE - No changes will be made")
        print("Use --apply to actually apply changes")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("APPLYING CHANGES")
        print("="*60)
    
    # Run migration
    stats = migrate(db, args.collection, query, dry_run)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Collection: {args.collection}")
    print(f"  Found: {stats['found']}")
    print(f"  {'Would update' if dry_run else 'Updated'}: {stats['updated']}")
    if stats['errors']:
        print(f"  Errors: {len(stats['errors'])}")
        for err in stats['errors']:
            print(f"    - {err}")
    
    if dry_run:
        print(f"\nThis was a DRY RUN. Use --apply to make changes.")
    else:
        print(f"\nMigration complete!")
    
    client.close()


if __name__ == "__main__":
    main()
