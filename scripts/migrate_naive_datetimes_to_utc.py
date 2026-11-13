#!/usr/bin/env python3
"""
Migration Script: Fix Datetime Strings to Include UTC Timezone Indicator

This script updates all datetime STRING fields in MongoDB collections to ensure they
have proper UTC timezone indicator ('Z' suffix). It also converts any datetime
objects back to strings (in case a previous migration incorrectly converted them).

The goal is to ensure all datetime fields are stored as ISO format STRINGS with
the 'Z' suffix, which is what the application code expects.

Usage:
    # Dry run (default) - shows what would be changed
    python migrate_naive_datetimes_to_utc.py
    
    # Actually perform the migration
    python migrate_naive_datetimes_to_utc.py --execute
    
    # Specify custom MongoDB connection
    python migrate_naive_datetimes_to_utc.py --mongo-uri "mongodb://localhost:27017/" --db-name "UnifAI"

Author: Migration script for timezone-aware datetime fix
"""

import argparse
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import pymongo
from pymongo import UpdateOne

# Default MongoDB connection settings
DEFAULT_MONGO_URI = "mongodb://10.46.254.131:27017/"
DEFAULT_DB_NAME = "UnifAI"

# Collection configurations: (collection_name, list of datetime field paths)
# Field paths use dot notation for nested fields
COLLECTION_DATETIME_FIELDS: Dict[str, List[str]] = {
    # Sessions collection
    "workflow_sessions": [
        "run_context.started_at",
        "run_context.finished_at",
    ],
    # Shares collection
    "shares": [
        "created_at",
        "accepted_at",
        "declined_at",
        "expires_at",
    ],
    # Blueprints collection
    "blueprints": [
        "created_at",
        "updated_at",
    ],
    # Templates collection
    "templates": [
        "created_at",
        "updated_at",
    ],
    # Pipeline records collection
    "pipeline_records": [
        "created_at",
        "last_updated",
    ],
    # Data sources collection
    "data_sources": [
        "created_at",
        "last_sync_at",
    ],
    # Resources collection
    "resources": [
        "created",
        "updated",
    ],
    # Terms approval collection
    "terms_approvals": [
        "approved_at",
        "created_at",
    ],
    # Monitoring metrics
    "monitoring_metrics": [
        "timestamp",
    ],
    # Monitoring errors
    "monitoring_errors": [
        "timestamp",
    ],
    # Monitoring logs
    "monitoring_logs": [
        "timestamp",
    ],
}


def get_nested_value(doc: Dict, path: str) -> Any:
    """Get a value from a nested dictionary using dot notation path."""
    keys = path.split(".")
    value = doc
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def datetime_to_iso_string(dt: datetime) -> str:
    """Convert a datetime object to ISO string with Z suffix."""
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to ISO format and replace +00:00 with Z
    return dt.isoformat().replace('+00:00', 'Z')


def needs_fix(value: Any) -> bool:
    """Check if a value needs to be fixed."""
    if value is None:
        return False
    
    # If it's a datetime object, it needs to be converted to string
    if isinstance(value, datetime):
        return True
    
    # If it's a string without timezone indicator, it needs Z suffix
    if isinstance(value, str):
        if value and 'T' in value:
            # Check if it's missing timezone indicators
            if not (value.endswith('Z') or '+' in value[-6:] or value.endswith('+00:00')):
                return True
    
    return False


def fix_value(value: Any) -> str:
    """Fix a datetime value to be a proper ISO string with Z suffix."""
    if isinstance(value, datetime):
        return datetime_to_iso_string(value)
    
    if isinstance(value, str):
        # String without timezone - add Z suffix
        if value and 'T' in value and not (value.endswith('Z') or '+' in value[-6:]):
            return value + 'Z'
    
    return value


def build_update_operations(
    collection: pymongo.collection.Collection,
    datetime_fields: List[str],
    dry_run: bool = True
) -> Tuple[List[UpdateOne], int, int]:
    """
    Build bulk update operations for a collection.
    
    Returns:
        Tuple of (update_operations, docs_to_update, total_fields_to_update)
    """
    operations = []
    docs_to_update = 0
    total_fields = 0
    
    cursor = collection.find({})
    
    for doc in cursor:
        update_dict = {}
        doc_needs_update = False
        
        for field_path in datetime_fields:
            value = get_nested_value(doc, field_path)
            
            if value is None:
                continue
            
            if needs_fix(value):
                new_value = fix_value(value)
                update_dict[field_path] = new_value
                doc_needs_update = True
                total_fields += 1
        
        if doc_needs_update:
            docs_to_update += 1
            if not dry_run:
                operations.append(
                    UpdateOne(
                        {"_id": doc["_id"]},
                        {"$set": update_dict}
                    )
                )
    
    return operations, docs_to_update, total_fields


def migrate_collection(
    db: pymongo.database.Database,
    collection_name: str,
    datetime_fields: List[str],
    dry_run: bool = True
) -> Tuple[int, int]:
    """
    Migrate a single collection's datetime fields to proper ISO strings with Z suffix.
    
    Returns:
        Tuple of (documents_updated, fields_updated)
    """
    if collection_name not in db.list_collection_names():
        print(f"  ⚠️  Collection '{collection_name}' does not exist, skipping...")
        return 0, 0
    
    collection = db[collection_name]
    total_docs = collection.count_documents({})
    
    print(f"\n📁 Processing collection: {collection_name}")
    print(f"   Total documents: {total_docs}")
    print(f"   Fields to check: {', '.join(datetime_fields)}")
    
    operations, docs_to_update, fields_to_update = build_update_operations(
        collection, datetime_fields, dry_run
    )
    
    if docs_to_update == 0:
        print(f"   ✅ No fixes needed - all datetime strings already have timezone")
        return 0, 0
    
    print(f"   📊 Found {docs_to_update} documents with {fields_to_update} datetime fields to fix")
    
    if dry_run:
        print(f"   🔍 DRY RUN - No changes made")
        return docs_to_update, fields_to_update
    
    # Execute bulk update
    if operations:
        result = collection.bulk_write(operations, ordered=False)
        print(f"   ✅ Updated {result.modified_count} documents")
        return result.modified_count, fields_to_update
    
    return 0, 0


def run_migration(mongo_uri: str, db_name: str, dry_run: bool = True):
    """Run the full migration across all configured collections."""
    print("=" * 70)
    print("🔄 MongoDB Datetime String Migration (Add UTC 'Z' Suffix)")
    print("=" * 70)
    print(f"\nConnection: {mongo_uri}")
    print(f"Database: {db_name}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else '⚡ EXECUTE (will modify data)'}")
    print(f"\nThis script will:")
    print(f"  - Convert datetime OBJECTS to ISO strings with 'Z' suffix")
    print(f"  - Add 'Z' suffix to datetime strings missing timezone info")
    print(f"  - Leave properly formatted strings unchanged")
    
    if not dry_run:
        print("\n⚠️  WARNING: This will modify data in your database!")
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Migration cancelled.")
            return
    
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client[db_name]
        
        # Test connection
        db.command('ping')
        print(f"\n✅ Connected to MongoDB successfully")
        
    except Exception as e:
        print(f"\n❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    total_docs_updated = 0
    total_fields_updated = 0
    collections_processed = 0
    
    for collection_name, datetime_fields in COLLECTION_DATETIME_FIELDS.items():
        docs, fields = migrate_collection(db, collection_name, datetime_fields, dry_run)
        total_docs_updated += docs
        total_fields_updated += fields
        collections_processed += 1
    
    print("\n" + "=" * 70)
    print("📈 Migration Summary")
    print("=" * 70)
    print(f"Collections processed: {collections_processed}")
    print(f"Documents {'to update' if dry_run else 'updated'}: {total_docs_updated}")
    print(f"Datetime fields {'to update' if dry_run else 'updated'}: {total_fields_updated}")
    
    if dry_run and total_docs_updated > 0:
        print(f"\n💡 To apply these changes, run with --execute flag:")
        print(f"   python {sys.argv[0]} --execute")
    elif not dry_run and total_docs_updated > 0:
        print(f"\n✅ Migration completed successfully!")
    else:
        print(f"\n✅ No migration needed - all datetime strings are properly formatted!")
    
    client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix datetime strings in MongoDB to include UTC 'Z' suffix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes)
  python migrate_naive_datetimes_to_utc.py
  
  # Execute migration
  python migrate_naive_datetimes_to_utc.py --execute
  
  # Custom MongoDB connection
  python migrate_naive_datetimes_to_utc.py --mongo-uri "mongodb://user:pass@host:27017/" --db-name "UnifAI" --execute
        """
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually execute the migration (default is dry-run)"
    )
    
    parser.add_argument(
        "--mongo-uri",
        default=DEFAULT_MONGO_URI,
        help=f"MongoDB connection URI (default: {DEFAULT_MONGO_URI})"
    )
    
    parser.add_argument(
        "--db-name",
        default=DEFAULT_DB_NAME,
        help=f"Database name (default: {DEFAULT_DB_NAME})"
    )
    
    args = parser.parse_args()
    
    run_migration(
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        dry_run=not args.execute
    )


if __name__ == "__main__":
    main()
