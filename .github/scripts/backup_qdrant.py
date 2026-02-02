#!/usr/bin/env python3
from qdrant_client import QdrantClient
import requests
import os
import sys
#constants to Qdrant cluster connection
QDRANT_MAIN_URL = os.getenv("QDRANT_URL")
QDRANT_PORT = 80
QDRANT_TIMEOUT = 30.0
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
SNAPSHOTS_DIR = os.getenv("QDRANT_SNAPSHOTS_DIR", "/tmp/snapshots")

def create_snapshots(node_url: str, collection_name: str) -> tuple[dict, str]:
    '''
    Creates a snapshot of the collection from the given node URLs

    Args:
        node_url: node URL to create the snapshot from
        collection_name: name of the collection to create the snapshot from
    Returns:
        snapshot URL
    '''

    try:
        print(node_url)
        print("collection name: ", collection_name)
        client = QdrantClient(url=node_url, port=QDRANT_PORT, api_key=QDRANT_API_KEY, prefer_grpc=False, timeout=QDRANT_TIMEOUT)
        print('created client - create snapshots')
        #node_client = QdrantClient(node_url, api_key=QDRANT_API_KEY)
        snapshot_info = client.create_snapshot(collection_name=collection_name, wait=True)
        print('created snapshot')
        #print(snapshot_info)
        snapshot_url = f"{node_url}/collections/{collection_name}/snapshots/{snapshot_info.name}"
        #snapshot_list.append({"collection_name": collection_name, "snapshot_url": snapshot_url})
        return snapshot_info, snapshot_url
    except PermissionError as e:
      # Access denied to collection
      print(f"Permission denied for collection {collection_name}: {e}")
      sys.exit(1)
    except RuntimeError as e:
      # Snapshot creation failed
      print(f"Failed to create snapshot: {e}")
      sys.exit(1)

def download_all_snapshots(snapshot_list: list[dict]) -> None:
    '''
    Downloads the snapshots from the given URLs and saves them to the local filesystem
    beforehand, checks if the directory exists and creates it if it doesn't

    Args:
        snapshot_urls: list of snapshot URLs to download
    Returns:
        list of local snapshot paths
    '''
    try:
        os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        print('creating snapshots directory')
        for snapshot in snapshot_list:
            snapshot_url = snapshot.get("snapshot_url")
            print("snapshot_url: ")
            print(snapshot_url)
            print('downloading snapshot: ', snapshot_url)
            snapshot_name = os.path.basename(snapshot.get("snapshot_info").name)
            local_snapshot_path = os.path.join(SNAPSHOTS_DIR, snapshot_name)

            response = requests.get(
                snapshot_url, headers={"api-key": QDRANT_API_KEY}
            )
            with open(local_snapshot_path, "wb") as f:
                response.raise_for_status()
                f.write(response.content)
        print('snapshots downloaded')
        print('snapshots directory: ', os.listdir(SNAPSHOTS_DIR))
    except requests.exceptions.HTTPError as e:
        # Already raised by raise_for_status()
        print(f"HTTP error downloading snapshot: {e}")
        sys.exit(1)
    except PermissionError as e:
        # Can't write to directory
        print(f"Permission denied writing to disk: {e}")           
        sys.exit(1)
    except OSError as e:
        # File writing issues, disk full, etc.
        print(f"Failed to write snapshot to disk: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error downloading snapshots: {e}")
        sys.exit(1)

def delete_snapshots(node_url: str, snapshot_list: list[dict]) -> None:
    '''
    Deletes the snapshots from the given URLs
    '''
    try:
        client = QdrantClient(url=node_url, port=QDRANT_PORT, api_key=QDRANT_API_KEY, prefer_grpc=False, timeout=QDRANT_TIMEOUT)
        for snapshot in snapshot_list:
            print('deleting snapshot: ', snapshot.get("snapshot_info").name)
            client.delete_snapshot(snapshot.get("collection_name"), snapshot.get("snapshot_info").name)
    except PermissionError as e:
      # Access denied to snapshot
      print(f"Permission denied for snapshot {snapshot.get('collection_name')}: {e}")
      sys.exit(1)
    except RuntimeError as e:
      # Snapshot deletion failed
      print(f"Failed to delete snapshot: {e}")
      sys.exit(1)    

def get_collections(node_url: str) -> list[object]:
    '''
    Gets the collections from the given node URL

    Args:
        node_url: node URL to get the collections from
    Returns:
        list of collections
    '''
    try:

        client = QdrantClient(url=node_url, port=QDRANT_PORT, api_key=QDRANT_API_KEY, prefer_grpc=False, timeout=QDRANT_TIMEOUT)
        collections = client.get_collections().collections
        print(collections)
        if not collections:
            raise ValueError(f"No collections found at {node_url}")
        return collections
    except ValueError as e:
        # Invalid URL or parameters
        print(f"Invalid configuration for {node_url}: {e}")
        sys.exit(1)
    except ConnectionError as e:
        print(f"Error connecting to {node_url}: {e}")
        sys.exit(1)
    except TimeoutError as e:
        print(f"Timeout connecting to {node_url}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error checking connection to {node_url}: {e}")
        sys.exit(1)

def main():
    '''
    Main function to run the backup
    '''
    collections = get_collections(QDRANT_MAIN_URL)
    #print(collections)
    if not collections:
        print(f"Error getting collections from {QDRANT_MAIN_URL}")
        return
    snapshot_list = []
    for collection in collections:
        print(collection)
        snapshot_info, snapshot_url = create_snapshots(QDRANT_MAIN_URL, collection.name)
        snapshot_list.append({"collection_name": collection.name, "snapshot_info": snapshot_info, "snapshot_url": snapshot_url})

    download_all_snapshots(snapshot_list)
    delete_snapshots(QDRANT_MAIN_URL, snapshot_list)

if __name__ == "__main__":
    main()