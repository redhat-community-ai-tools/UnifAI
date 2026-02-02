import os
import shutil
import sys
from pathlib import Path
from git import Repo
from git.remote import RemoteProgress

# Environment variables
BACKUP_REPO = os.getenv("BACKUP_REPO")
BACKUP_REPO_NAME = os.getenv("BACKUP_REPO_NAME")
#MONGO_BACKUP_FILE = os.getenv("MONGO_BACKUP_FILE")
QDRANT_SNAPSHOTS_DIR = os.getenv("QDRANT_SNAPSHOTS_DIR")


def find_mongo_backup_file(path: str ) -> list[str]:
    """
    Find the mongo backup file in the local filesystem
    """
    try:
        matches: list[str] = []
        for file in os.listdir(path):
            if file.startswith("mongo_backup"):
                matches.append(os.path.join(path, file))
        return matches
    except FileNotFoundError as e:
        print(f"Mongo backup file not found: {e}")
        return []
        #sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        return []
        #sys.exit(1)

def upload_to_gitlab():
    """
    Upload backup files to GitLab repository
    Equivalent to upload_to_gitlab.sh
    """

    mongo_backup_files = []
    # Validate required environment variables
    required_vars = {
        "BACKUP_REPO": BACKUP_REPO,
        "BACKUP_REPO_NAME": BACKUP_REPO_NAME,
        "QDRANT_SNAPSHOTS_DIR": QDRANT_SNAPSHOTS_DIR
    }
    
    for var_name, var_value in required_vars.items():
        if not var_value:
            raise ValueError(f"{var_name} environment variable is required")
    
    try:
        # Clone repository
        print("Cloning gitlab repo")
        repo = Repo.clone_from(BACKUP_REPO, BACKUP_REPO_NAME, depth=1)
        print("Cloned gitlab repo")
        
        #delete older mongo backups
        older_mongo_backup_files = find_mongo_backup_file(BACKUP_REPO_NAME)
        # if older_mongo_backup_files is not None:
        for file in older_mongo_backup_files:
            print(f"Deleting older mongo backup file: {file}")
            os.remove(file)

        # Copy mongo backup file
        print("Copying mongo backup file to gitlab repo")
        mongo_backup_files = find_mongo_backup_file("/tmp")
        if not mongo_backup_files:
            print("Mongo backup file not found")
            sys.exit(1)
        else:
            for file in mongo_backup_files:
                print(f"Copying mongo backup file: {file}")
                shutil.copy(file, BACKUP_REPO_NAME)
        
        # Copy qdrant snapshots directory
        print("Copying qdrant snapshots to gitlab repo")
        #snapshots_dirname = os.path.basename(QDRANT_SNAPSHOTS_DIR)
        snapshots_dirname = Path(QDRANT_SNAPSHOTS_DIR).resolve().name
        if not snapshots_dirname:
            raise ValueError("QDRANT_SNAPSHOTS_DIR must not be filesystem root")        
        dest_snapshots_path = os.path.join(BACKUP_REPO_NAME, snapshots_dirname)
        
        # Remove old snapshots directory if exists
        if os.path.exists(dest_snapshots_path):
            print("Removing old snapshots directory")
            shutil.rmtree(dest_snapshots_path)
        
        # Copy new snapshots
        shutil.copytree(QDRANT_SNAPSHOTS_DIR, dest_snapshots_path)
        print("Copied files to gitlab repo")
        
        # Configure git user
        print("Committing changes to gitlab repo")
        with repo.config_writer() as git_config:
            git_config.set_value('user', 'email', 'github_actions@users.noreply.gitlab.cee.redhat.com')
            git_config.set_value('user', 'name', 'github_actions')
        
        # Add all changes
        repo.git.add(A=True)
        
        # Commit
        repo.index.commit("uploading backup files to gitlab")
        print("Committed changes")
        
        # Push
        origin = repo.remote(name='origin')
        origin.push()
        print("Pushed changes to gitlab repo")
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        print("Cleaning up")
        for file in mongo_backup_files:
          if os.path.exists(file):
            os.remove(file)
        if QDRANT_SNAPSHOTS_DIR and os.path.exists(QDRANT_SNAPSHOTS_DIR):
            shutil.rmtree(QDRANT_SNAPSHOTS_DIR)
        if BACKUP_REPO_NAME and os.path.exists(BACKUP_REPO_NAME):
            shutil.rmtree(BACKUP_REPO_NAME)
        print("Uploading files to gitlab repo completed")


if __name__ == "__main__":
    upload_to_gitlab()