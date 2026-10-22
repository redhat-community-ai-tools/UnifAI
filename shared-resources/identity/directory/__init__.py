from directory.models import DirectoryUser, DirectoryGroup, LdapConfig, OidcClaimsConfig
from directory.provider import DirectoryProvider


def __getattr__(name: str):
    """Lazy-load concrete adapters so that ``ldap3`` is only required
    by services that actually use them."""
    if name == "LdapDirectoryProvider":
        from directory.ldap_provider import LdapDirectoryProvider
        return LdapDirectoryProvider
    if name == "OidcClaimsDirectoryProvider":
        from directory.oidc_claims_provider import OidcClaimsDirectoryProvider
        return OidcClaimsDirectoryProvider
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DirectoryUser",
    "DirectoryGroup",
    "DirectoryProvider",
    "LdapConfig",
    "OidcClaimsConfig",
    "OidcClaimsDirectoryProvider",
    "LdapDirectoryProvider",
]
