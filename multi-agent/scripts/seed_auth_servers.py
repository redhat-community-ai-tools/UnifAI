#!/usr/bin/env python3
"""
Seed pre-configured auth servers into the server_configs collection.

All sensitive values (client_secret) come from environment variables populated
by Helm/Vault at deploy time. Endpoint URLs use Red Hat SSO defaults but can
be overridden via env vars. This script is idempotent — safe to run on every
deployment.

Usage:
  export MONGODB_IP=mongodb
  export MONGODB_PORT=27017
  export MONGO_DB=UnifAI
  export A2A_SSO_STAGING_CLIENT_ID="unifai-a2a"
  export A2A_SSO_STAGING_CLIENT_SECRET="<from vault>"
  export A2A_SSO_PROD_CLIENT_ID="unifai-a2a"
  export A2A_SSO_PROD_CLIENT_SECRET="<from vault>"
  python scripts/seed_auth_servers.py
"""

from __future__ import annotations

import os
import sys

from pymongo import MongoClient, ASCENDING

MONGODB_IP = os.environ.get("MONGODB_IP", "127.0.0.1")
MONGODB_PORT = int(os.environ.get("MONGODB_PORT", "27017"))
MONGO_DB = os.environ.get("MONGO_DB", "UnifAI")
COLL_NAME = os.environ.get("SERVER_CONFIGS_COLL", "server_configs")

# Red Hat SSO base URLs and realm
_RH_SSO_STAGE_BASE = "https://auth.stage.redhat.com/auth"
_RH_SSO_PROD_BASE = "https://auth.redhat.com/auth"
_RH_SSO_REALM = "EmployeeIDP"

_STAGE_OIDC = f"{_RH_SSO_STAGE_BASE}/realms/{_RH_SSO_REALM}/protocol/openid-connect"
_PROD_OIDC = f"{_RH_SSO_PROD_BASE}/realms/{_RH_SSO_REALM}/protocol/openid-connect"


def _build_server_entries() -> list:
    """
    Build the list of auth server entries from environment variables.

    Each SSO environment needs:
      - *_CLIENT_ID (required — skip entry if missing)
      - *_CLIENT_SECRET (from Vault)
      - *_AUTH_ENDPOINT (optional override, defaults to Red Hat SSO)
      - *_TOKEN_ENDPOINT (optional override, defaults to Red Hat SSO)
      - *_SCOPES (space-separated, defaults to "openid profile email")
      - *_DISPLAY_NAME (human label for the UI dropdown)
      - *_CATEGORIES (comma-separated, defaults to "a2a")
    """
    entries = []

    prefixes = {
        "A2A_SSO_STAGING": {
            "server_identifier": "rh-sso-staging",
            "display_name_default": "Red Hat SSO (Staging)",
            "categories_default": "a2a",
            "auth_endpoint_default": f"{_STAGE_OIDC}/auth",
            "token_endpoint_default": f"{_STAGE_OIDC}/token",
        },
        "A2A_SSO_PROD": {
            "server_identifier": "rh-sso-prod",
            "display_name_default": "Red Hat SSO (Production)",
            "categories_default": "a2a",
            "auth_endpoint_default": f"{_PROD_OIDC}/auth",
            "token_endpoint_default": f"{_PROD_OIDC}/token",
        },
    }

    for prefix, defaults in prefixes.items():
        client_id = os.environ.get(f"{prefix}_CLIENT_ID", "")
        if not client_id:
            continue

        entries.append({
            "server_identifier": defaults["server_identifier"],
            "display_name": os.environ.get(
                f"{prefix}_DISPLAY_NAME", defaults["display_name_default"]
            ),
            "categories": os.environ.get(
                f"{prefix}_CATEGORIES", defaults["categories_default"]
            ).split(","),
            "client_id": client_id,
            "client_secret": os.environ.get(f"{prefix}_CLIENT_SECRET"),
            "authorization_endpoint": os.environ.get(
                f"{prefix}_AUTH_ENDPOINT", defaults["auth_endpoint_default"]
            ),
            "token_endpoint": os.environ.get(
                f"{prefix}_TOKEN_ENDPOINT", defaults["token_endpoint_default"]
            ),
            "token_endpoint_auth_method": os.environ.get(
                f"{prefix}_TOKEN_AUTH_METHOD", "client_secret_post"
            ),
            "scopes": os.environ.get(f"{prefix}_SCOPES", "openid profile email").split(),
            "protocol_type": "oauth2",
        })

    return entries


def main() -> None:
    entries = _build_server_entries()
    if not entries:
        print("No auth server entries configured (missing *_CLIENT_ID env vars). Nothing to seed.")
        sys.exit(0)

    client = MongoClient(f"mongodb://{MONGODB_IP}:{MONGODB_PORT}/")
    coll = client[MONGO_DB][COLL_NAME]

    coll.create_index(
        [("server_identifier", ASCENDING)],
        unique=True,
        name="uq_server_identifier",
    )
    coll.create_index(
        [("categories", ASCENDING)],
        name="idx_categories",
        sparse=True,
    )

    print(f"Seeding {len(entries)} auth server(s) into {MONGO_DB}.{COLL_NAME}...")

    for entry in entries:
        sid = entry["server_identifier"]
        coll.update_one(
            {"server_identifier": sid},
            {"$set": entry},
            upsert=True,
        )
        print(f"  ✓ {entry['display_name']} ({sid})")

    print("\nSeed complete.")


if __name__ == "__main__":
    main()
