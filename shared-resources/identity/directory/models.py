from typing import List

from pydantic import BaseModel, Field


class DirectoryUser(BaseModel):
    """A user record from an external directory (e.g. LDAP, SSO user-store)."""
    user_id: str
    username: str
    display_name: str
    email: str = ""
    title: str = ""


class DirectoryGroup(BaseModel):
    """A group record from an external directory (e.g. LDAP ou=groups)."""
    group_id: str
    name: str
    description: str = ""
    members: List[str] = Field(default_factory=list)


class LdapConfig(BaseModel):
    url: str
    user_base_dn: str
    bind_dn: str = ""
    bind_password: str = ""
    skip_tls_verify: bool = False
    timeout_seconds: int = 10
    pool_size: int = 5

    # user attributes
    attr_uid: str = "uid"
    attr_cn: str = "cn"
    attr_mail: str = "mail"
    attr_title: str = "title"
    # Default matches historical sso-backend (factory did not override this).
    user_object_class: str = "person"
    # Extra attributes appended to the uid/cn/mail substring OR (see ldap_provider).
    user_search_attrs: str = "uid,cn,mail"

    # group settings (empty base DN disables group queries)
    group_base_dn: str = ""
    group_object_class: str = "groupOfUniqueNames"
    attr_group_cn: str = "cn"
    attr_group_description: str = "description"
    attr_group_member: str = "uniqueMember"


class OidcClaimsConfig(BaseModel):
    """Settings for the ``oidc-claims`` directory provider."""
    # Claim holding the group list; a dotted path (``realm_access.roles``)
    # is resolved when no claim has that exact name.
    claim: str = "groups"
    # Claim that must equal the user being queried.
    username_claim: str = "preferred_username"
    # Removed from the start of each group after the leading ``/`` is stripped.
    group_prefix: str = ""
    # Case is preserved by default; set to match case-insensitively.
    lowercase: bool = False
    # Token verification is mandatory: JWKS endpoint and expected issuer.
    jwks_url: str
    issuer: str
    # Checked only when set (Keycloak access tokens often carry ``aud=account``).
    audience: str = ""
