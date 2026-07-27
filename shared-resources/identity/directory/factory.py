"""
Directory provider factory.

Selects the concrete directory adapter based on the application config.
New backends (Azure AD, etc.) are added here as additional branches.
"""
import logging
from typing import Optional

from directory.provider import DirectoryProvider

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = {"ldap"}


def _is_placeholder_user_base_dn(user_base_dn: str) -> bool:
    """True when *user_base_dn* is clearly an example / template, not a real naming context."""
    ub = (user_base_dn or "").lower().strip()
    if not ub:
        return True
    # Copy-paste defaults from docs / samples (logs often show ``dc=your,dc=base``).
    if "dc=your" in ub or "your,dc=base" in ub:
        return True
    return False


def _naming_suffix_from_first_dc(dn: str) -> Optional[str]:
    """Return the subtree from the first ``dc=`` RDN onward, e.g. ``dc=redhat,dc=com``."""
    parts = [p.strip() for p in dn.split(",") if p.strip()]
    for i, p in enumerate(parts):
        if p.lower().startswith("dc="):
            return ",".join(parts[i:])
    return None


def _group_base_ok_for_deriving_user_base(group_base_dn: str) -> bool:
    if not (group_base_dn or "").strip():
        return False
    # Do not derive from another template group DN
    if _is_placeholder_user_base_dn(group_base_dn):
        return False
    return _naming_suffix_from_first_dc(group_base_dn) is not None


def effective_ldap_user_base_dn(
    user_base_dn: str,
    group_base_dn: str,
    *,
    user_rdn_ou: str = "ou=users",
) -> tuple[str, bool]:
    """Return ``(effective_user_base, derived)``.

    When *user_base_dn* is a placeholder and *group_base_dn* is a real DN, derive
    ``{user_rdn_ou},{suffix}`` where *suffix* is the naming context taken from the
    group base (from the first ``dc=`` component). This matches deployments where
    ``DIRECTORY_LDAP_GROUP_BASE_DN`` is correct but ``DIRECTORY_LDAP_USER_BASE_DN``
    was left at a copy-pasted example (common cause: groups work, users do not).
    """
    raw = (user_base_dn or "").strip()
    group = (group_base_dn or "").strip()
    ou = (user_rdn_ou or "ou=users").strip() or "ou=users"

    if not _is_placeholder_user_base_dn(raw):
        return raw, False
    if not _group_base_ok_for_deriving_user_base(group):
        return raw, False
    suffix = _naming_suffix_from_first_dc(group)
    if not suffix:
        return raw, False
    derived = f"{ou},{suffix}"
    logger.warning(
        "LDAP directory_ldap_user_base_dn=%r looks like a placeholder; derived "
        "user_base_dn=%r from group_base and user_rdn_ou=%r. Set "
        "DIRECTORY_LDAP_USER_BASE_DN explicitly to a real subtree to override.",
        raw,
        derived,
        ou,
    )
    return derived, True


def _warn_if_user_base_still_placeholder(user_base_dn: str) -> None:
    if _is_placeholder_user_base_dn(user_base_dn):
        logger.warning(
            "directory_ldap_user_base_dn=%r still looks like a placeholder and could "
            "not be derived from group_base — user LDAP search will return no results. "
            "Set DIRECTORY_LDAP_USER_BASE_DN to the real user subtree (same DC suffix as groups).",
            user_base_dn,
        )


def build_directory_provider(cfg) -> Optional[DirectoryProvider]:
    """Build the directory provider specified by *cfg.directory_provider*."""
    provider_name = cfg.directory_provider.strip().lower()
    if not provider_name:
        return None

    if provider_name not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unknown directory_provider: '{provider_name}'. "
            f"Supported: {', '.join(sorted(_SUPPORTED_PROVIDERS))}"
        )

    if provider_name == "ldap":
        return _build_ldap(cfg)

    return None


def _build_ldap(cfg) -> DirectoryProvider:
    from directory import LdapDirectoryProvider, LdapConfig

    if not cfg.directory_url:
        raise ValueError("directory_url is required when directory_provider='ldap'")
    if not cfg.directory_ldap_user_base_dn:
        raise ValueError(
            "directory_ldap_user_base_dn is required when directory_provider='ldap'"
        )

    user_rdn_ou = getattr(cfg, "directory_ldap_user_rdn_ou", None) or "ou=users"
    user_base, _derived = effective_ldap_user_base_dn(
        cfg.directory_ldap_user_base_dn,
        cfg.directory_ldap_group_base_dn,
        user_rdn_ou=user_rdn_ou,
    )
    _warn_if_user_base_still_placeholder(user_base)

    ldap_cfg = LdapConfig(
        url=cfg.directory_url,
        user_base_dn=user_base,
        bind_dn=cfg.directory_ldap_bind_dn,
        bind_password=cfg.directory_ldap_bind_password,
        skip_tls_verify=not cfg.directory_verify_ssl,
        timeout_seconds=cfg.directory_timeout,
        user_object_class=cfg.directory_ldap_user_object_class,
        user_search_attrs=cfg.directory_ldap_user_search_attrs,
        group_base_dn=cfg.directory_ldap_group_base_dn,
        group_object_class=cfg.directory_ldap_group_object_class,
        attr_group_member=cfg.directory_ldap_group_member_attr,
    )
    logger.info("Directory provider: ldap (%s)", cfg.directory_url)
    return LdapDirectoryProvider(config=ldap_cfg)
