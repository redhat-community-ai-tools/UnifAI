from pathlib import Path
from typing import Any, Dict, Type

import yaml
from dotenv import dotenv_values
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from global_utils.config.config import SharedConfig
from global_utils.config.sources import JsonSource, YamlSource

_IDENTITY_ROOT = Path(__file__).resolve().parent.parent
_IDENTITY_ENV_FILE = _IDENTITY_ROOT / ".env"
_IDENTITY_DIRECTORY_YAML = _IDENTITY_ROOT / "directory.yaml"

class AppConfig(SharedConfig):
    # App Configuration
    app_name: str = "identity"
    hostname_local: str = "0.0.0.0"
    port: str = "13456"
    secret_key: str = ""

    # Local auth (dev bypass -- set via local-development env_generator)
    local_auth_enabled: bool = False

    # Keycloak Configuration
    keycloak_base_url: str = ""
    client_id: str = ""
    client_secret: str = ""
    keycloak_realm: str = ""
    version: str = "1.0.0"
    admin_allowed_users: list = []  # Populate with user_ids (usernames) to grant admin access

    frontend_url: str = "http://localhost:5000"    
    backend_env: str = "development"

    # Multi-agent connection
    multiagent_host: str = "localhost"
    multiagent_port: str = "8002"

    # Session Configuration
    session_cookie_secure: bool = True
    session_cookie_http_only: bool = True
    session_cookie_samesite: str = "None"
    permanent_session_lifetime: int = 10

    # MongoDB — teams collection (lives in the "users" DB alongside user approval terms)
    mongo_db: str = "users"
    teams_coll: str = "teams"

    # ── LDAP / Directory settings ──────────────────────────────────────────
    # Stable LDAP structural params (base DNs, object classes, search attrs)
    # are intentional defaults here — not injected from env. Only override via
    # env var if the target directory schema changes.
    #
    # Environment-specific connection settings (directory_provider, directory_url,
    # directory_verify_ssl) are injected at deploy time via the identity-config
    # ConfigMap (see helm/scripts/identity-presync.sh).
    #
    # Bind credentials (directory_ldap_bind_dn, directory_ldap_bind_password)
    # default to empty (anonymous bind). A future story will move these to a
    # Kubernetes Secret.
    directory_provider: str = ""
    directory_url: str = ""
    directory_timeout: int = 10
    directory_verify_ssl: bool = True

    # LDAP-specific settings (used when directory_provider="ldap")
    directory_ldap_user_base_dn: str = "ou=users,dc=redhat,dc=com"
    # Used only when user_base_dn looks like a template but group_base_dn is real:
    # effective user base becomes ``{this},{suffix_from_group}`` (default RH: ou=users).
    directory_ldap_user_rdn_ou: str = "ou=users"
    directory_ldap_group_base_dn: str = "ou=adhoc,ou=managedGroups,dc=redhat,dc=com"
    directory_ldap_group_object_class: str = "groupOfUniqueNames,rhatRoverGroup"
    directory_ldap_group_member_attr: str = "uniqueMember"
    # Default matches proven sso-backend behavior; set to e.g. inetOrgPerson,person if needed.
    directory_ldap_user_object_class: str = "person"
    # Appended to uid/cn/mail in user substring search; add rhatPreferredAlias for RH if desired.
    directory_ldap_user_search_attrs: str = "uid,cn,mail"
    directory_ldap_bind_dn: str = ""
    directory_ldap_bind_password: str = ""

    # User-groups cache TTL (seconds). Groups are fetched on login and
    # cached in Redis so we don't hit LDAP on every request.
    user_groups_cache_ttl: int = 3600
    # Directory lookup cache TTL (seconds).
    directory_cache_ttl: int = 120
