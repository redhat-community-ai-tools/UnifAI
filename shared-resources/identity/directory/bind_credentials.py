"""
LDAP bind-credential helpers.

Pure string/DN normalization with no ``ldap3`` or adapter dependency, so this
module can be imported at module scope from anywhere in ``directory`` (e.g.
``factory.py``) without pulling in ``ldap3`` and without breaking the lazy
``ldap3`` loading in ``directory/__init__.py``.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def prepare_ldap_bind_credentials(
    bind_dn: str,
    bind_password: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize bind DN/password for ldap3 SIMPLE bind.

    *bind_dn* must be the **full** LDAP distinguished name as returned by IPA /
    ROVER (commas are part of the DN and must be preserved)

    Only leading/trailing whitespace is stripped — never split or rewrite the DN.
    Returns ``(None, None)`` when *bind_dn* is empty (anonymous bind).
    """
    dn = (bind_dn or "").strip()
    password = (bind_password or "").strip()
    if not dn:
        return None, None
    if "=" not in dn:
        logger.warning("directory_ldap_bind_dn=%r does not look like a full DN", dn)
    if not password:
        logger.warning("directory_ldap_bind_dn is set but bind password is empty")
    return dn, password or None


def ldap_bind_dn_log_label(bind_dn: Optional[str]) -> str:
    """Short label for logs — first RDN value only, not the full DN."""
    if not bind_dn:
        return "anonymous"
    first_rdn = bind_dn.split(",", 1)[0].strip()
    if "=" in first_rdn:
        return first_rdn.split("=", 1)[1]
    return first_rdn
