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

Local/lab IdPs (http or private-IP token URLs), also set:
  export ALLOW_INSECURE_OAUTH_ENDPOINTS=1
http://localhost and http://127.0.0.1 are always allowed without that flag.
"""

from __future__ import annotations

import os
import sys

from pymongo import MongoClient, ASCENDING

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MULTI_AGENT_ROOT = os.path.dirname(SCRIPT_DIR)
if MULTI_AGENT_ROOT not in sys.path:
    sys.path.insert(0, MULTI_AGENT_ROOT)

LIB_DIR = os.path.join(MULTI_AGENT_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from mas.core.auth.credentials.models import ClientConfig

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


def _build_server_entries() -> list[ClientConfig]:
    """
    Build the list of auth server configs from environment variables.

    Each SSO environment needs:
      - *_CLIENT_ID (required — skip entry if missing)
      - *_CLIENT_SECRET (from Vault)
      - *_AUTH_ENDPOINT (optional override, defaults to Red Hat SSO)
      - *_TOKEN_ENDPOINT (optional override, defaults to Red Hat SSO)
      - *_SCOPES (space-separated, defaults to "openid profile email")
      - *_DISPLAY_NAME (human label for the UI dropdown)
      - *_CATEGORIES (comma-separated, defaults to "a2a")
    """
    entries: list[ClientConfig] = []

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

        client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET")
        token_auth_method = os.environ.get(
            f"{prefix}_TOKEN_AUTH_METHOD", "client_secret_post"
        )
        if token_auth_method == "client_secret_post" and not client_secret:
            raise ValueError(
                f"Cannot seed {prefix}: {prefix}_CLIENT_SECRET is required "
                "for client_secret_post"
            )

        entries.append(
            ClientConfig(
                server_identifier=defaults["server_identifier"],
                display_name=os.environ.get(
                    f"{prefix}_DISPLAY_NAME", defaults["display_name_default"]
                ),
                categories=[
                    c.strip()
                    for c in os.environ.get(
                        f"{prefix}_CATEGORIES", defaults["categories_default"]
                    ).split(",")
                    if c.strip()
                ],
                client_id=client_id,
                client_secret=client_secret,
                authorization_endpoint=os.environ.get(
                    f"{prefix}_AUTH_ENDPOINT", defaults["auth_endpoint_default"]
                ),
                token_endpoint=os.environ.get(
                    f"{prefix}_TOKEN_ENDPOINT", defaults["token_endpoint_default"]
                ),
                token_endpoint_auth_method=token_auth_method,
                scopes=os.environ.get(f"{prefix}_SCOPES", "openid profile email").split(),
                protocol_type="oauth2",
            )
        )

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

    for config in entries:
        entry = config.model_dump()
        sid = config.server_identifier
        coll.update_one(
            {"server_identifier": sid},
            {"$set": entry},
            upsert=True,
        )
        print(f"  ✓ {config.display_name} ({sid})")

    print("\nSeed complete.")


if __name__ == "__main__":
    main()
