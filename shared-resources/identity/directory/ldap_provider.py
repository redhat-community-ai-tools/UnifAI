"""
LDAP adapter for DirectoryProvider.

Queries the corporate LDAP directory for user and group information.
Requires the ``ldap3`` package.
"""
import logging
import threading
import time
from typing import List, Optional, Tuple

import ldap3
from ldap3 import Server, ServerPool, Connection, SUBTREE, ROUND_ROBIN
from ldap3.core.exceptions import LDAPException

from directory.models import DirectoryUser, DirectoryGroup
from directory.provider import DirectoryProvider
from directory.models import LdapConfig

logger = logging.getLogger(__name__)

_CACHE_TTL = 30  # seconds


class _ResultCache:
    """Thread-safe TTL cache for LDAP search results."""

    def __init__(self, ttl: int = _CACHE_TTL):
        self._ttl = ttl
        self._store: dict[str, Tuple[float, list]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[list]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                del self._store[key]
                return None
            return value

    def put(self, key: str, value: list) -> None:
        now = time.monotonic()
        with self._lock:
            self._store[key] = (now, value)
            if len(self._store) > 500:
                self._evict(now)

    def _evict(self, now: float) -> None:
        expired = [k for k, (ts, _) in self._store.items()
                   if now - ts > self._ttl]
        for k in expired:
            del self._store[k]


class LdapDirectoryProvider(DirectoryProvider):
    def __init__(self, config: LdapConfig):
        self._cfg = config
        self._user_base = config.user_base_dn
        self._user_attrs = self._build_user_ldap_attribute_list(config)

        self._group_base = config.group_base_dn or None
        self._group_attrs = [
            config.attr_group_cn,
            config.attr_group_description,
            config.attr_group_member,
        ]

        tls = None
        if config.url.startswith("ldaps"):
            tls = ldap3.Tls(validate=0 if config.skip_tls_verify else 2)

        urls = [u.strip() for u in config.url.split(",") if u.strip()]
        servers = [
            Server(u, use_ssl=u.startswith("ldaps"), tls=tls,
                   connect_timeout=config.timeout_seconds)
            for u in urls
        ]
        self._pool = ServerPool(servers, ROUND_ROBIN, active=True)

        self._bind_dn = config.bind_dn or None
        self._bind_pw = config.bind_password or None
        self._timeout = config.timeout_seconds

        self._conn: Optional[Connection] = None
        self._conn_lock = threading.Lock()
        self._cache = _ResultCache()

        logger.info(
            "LDAP provider: %s, user_base=%s, group_base=%s, bind=%s",
            config.url, self._user_base,
            self._group_base or "(disabled)",
            self._bind_dn or "anonymous",
        )

    @staticmethod
    def _build_user_ldap_attribute_list(config: LdapConfig) -> list:
        """Request all attributes referenced in user search and display mapping."""
        names: list[str] = []
        seen: set[str] = set()
        for raw in (
            config.attr_uid,
            config.attr_cn,
            config.attr_mail,
            config.attr_title,
            *(
                a.strip()
                for a in config.user_search_attrs.split(",")
                if a.strip()
            ),
        ):
            if raw and raw not in seen:
                seen.add(raw)
                names.append(raw)
        return names

    def _get_connection(self) -> Connection:
        """Return a reusable connection, reconnecting only when necessary."""
        with self._conn_lock:
            return self._get_locked_connection()

    def _get_locked_connection(self) -> Connection:
        """Like ``_get_connection`` but assumes ``_conn_lock`` is already held."""
        if self._conn is not None:
            try:
                if self._conn.bound:
                    return self._conn
            except Exception:
                pass
            try:
                self._conn.unbind()
            except Exception:
                pass

        conn = Connection(
            self._pool,
            user=self._bind_dn,
            password=self._bind_pw,
            auto_bind=True,
            read_only=True,
            receive_timeout=self._timeout,
        )
        self._conn = conn
        return conn

    def _search(self, base_dn: str, search_filter: str,
                attributes: list, limit: int = 0) -> list:
        cache_key = f"{base_dn}|{search_filter}|{limit}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("LDAP cache hit: %s", cache_key)
            return cached

        with self._conn_lock:
            try:
                conn = self._get_locked_connection()
                conn.search(
                    search_base=base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=attributes,
                    size_limit=limit,
                )
                results = [
                    entry for entry in conn.entries
                    if str(entry.entry_dn) != base_dn
                ]
                logger.debug(
                    "LDAP search base=%s filter=%s → %d result(s)",
                    base_dn, search_filter, len(results),
                )
                self._cache.put(cache_key, results)
                return results
            except LDAPException:
                logger.exception(
                    "LDAP search failed: base=%s filter=%s", base_dn, search_filter,
                )
                try:
                    if self._conn is not None:
                        self._conn.unbind()
                except Exception:
                    pass
                self._conn = None
                return []

    @staticmethod
    def _escape(value: str) -> str:
        return ldap3.utils.conv.escape_filter_chars(value)

    # ── user helpers ───────────────────────────────────────────────────

    def _user_object_class_filter(self) -> str:
        """Build objectClass filter for users (comma-separated like group_object_class)."""
        classes = [c.strip() for c in self._cfg.user_object_class.split(",") if c.strip()]
        if not classes:
            return "(objectClass=person)"
        if len(classes) == 1:
            return f"(objectClass={classes[0]})"
        return "(|" + "".join(f"(objectClass={c})" for c in classes) + ")"

    def _entry_to_user(self, entry) -> DirectoryUser:
        attrs = entry.entry_attributes_as_dict
        uid = _first(attrs.get(self._cfg.attr_uid, []))
        cn = _first(attrs.get(self._cfg.attr_cn, []))
        mail = _first(attrs.get(self._cfg.attr_mail, []))
        title = _first(attrs.get(self._cfg.attr_title, []))

        login = uid
        if not login:
            for name in self._cfg.user_search_attrs.split(","):
                key = name.strip()
                if not key or key == self._cfg.attr_uid:
                    continue
                login = _first(attrs.get(key, []))
                if login:
                    break

        return DirectoryUser(
            user_id=uid or login or cn or "",
            username=uid or login or cn or "",
            display_name=cn or uid or login or "",
            email=mail or "",
            title=title or "",
        )

    def _user_name_substrings_filter(self, q: str) -> str:
        """Substring OR filter for user search.

        Always includes ``attr_uid``, ``attr_cn``, and ``attr_mail`` first — matching
        the historical ``sso-backend`` filter — then any extra attributes from
        ``user_search_attrs`` (deduped). That way optional attrs (e.g. RH-specific
        aliases) cannot accidentally replace the core triple or omit ``mail``.
        """
        core_attrs = [
            self._cfg.attr_uid,
            self._cfg.attr_cn,
            self._cfg.attr_mail,
        ]
        ordered: list[str] = []
        seen_lower: set[str] = set()
        for attr in core_attrs:
            a = (attr or "").strip()
            if not a:
                continue
            low = a.lower()
            if low in seen_lower:
                continue
            seen_lower.add(low)
            ordered.append(a)
        for raw in self._cfg.user_search_attrs.split(","):
            a = raw.strip()
            if not a:
                continue
            low = a.lower()
            if low in seen_lower:
                continue
            seen_lower.add(low)
            ordered.append(a)
        if not ordered:
            ordered.append((self._cfg.attr_uid or "uid").strip() or "uid")
        return "(|" + "".join(f"({a}=*{q}*)" for a in ordered) + ")"

    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        q = self._escape(query)
        oc_filter = self._user_object_class_filter()
        name_filter = self._user_name_substrings_filter(q)
        search_filter = f"(&{oc_filter}{name_filter})"
        logger.info(
            "LDAP user search: base=%s filter=%s",
            self._user_base, search_filter,
        )
        entries = self._search(self._user_base, search_filter,
                               self._user_attrs, limit=limit)
        users = [self._entry_to_user(e) for e in entries]
        # Match legacy sso-backend: return mapped entries; drop only completely empty rows.
        return [u for u in users if u.user_id or u.username or u.display_name]

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        q = self._escape(user_id)
        oc_filter = self._user_object_class_filter()
        or_parts = [f"({self._cfg.attr_uid}={q})"]
        for raw in self._cfg.user_search_attrs.split(","):
            attr = raw.strip()
            if attr and attr != self._cfg.attr_uid:
                or_parts.append(f"({attr}={q})")
        id_filter = "(|" + "".join(or_parts) + ")"
        search_filter = f"(&{oc_filter}{id_filter})"
        entries = self._search(self._user_base, search_filter,
                               self._user_attrs, limit=1)
        if not entries:
            return None
        return self._entry_to_user(entries[0])

    # ── group helpers ──────────────────────────────────────────────────

    def _entry_to_group(self, entry) -> DirectoryGroup:
        attrs = entry.entry_attributes_as_dict
        cn = _first(attrs.get(self._cfg.attr_group_cn, []))
        description = _first(attrs.get(self._cfg.attr_group_description, []))
        raw_members = attrs.get(self._cfg.attr_group_member, [])
        members = [_dn_to_uid(str(m)) for m in raw_members if m]

        return DirectoryGroup(
            group_id=cn or "",
            name=cn or "",
            description=description or "",
            members=members,
        )

    def _object_class_filter(self) -> str:
        """Build objectClass filter supporting comma-separated values."""
        classes = [c.strip() for c in self._cfg.group_object_class.split(",") if c.strip()]
        if len(classes) == 1:
            return f"(objectClass={classes[0]})"
        return "(|" + "".join(f"(objectClass={c})" for c in classes) + ")"

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        if not self._group_base:
            return []
        q = self._escape(query)
        cn = self._cfg.attr_group_cn
        oc_filter = self._object_class_filter()
        search_filter = f"(&{oc_filter}({cn}=*{q}*))"
        logger.info(
            "LDAP group search: base=%s filter=%s",
            self._group_base, search_filter,
        )
        entries = self._search(self._group_base, search_filter,
                               self._group_attrs, limit=limit)
        return [self._entry_to_group(e) for e in entries]

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        if not self._group_base:
            return None
        q = self._escape(group_id)
        oc_filter = self._object_class_filter()
        search_filter = f"(&{oc_filter}({self._cfg.attr_group_cn}={q}))"
        entries = self._search(self._group_base, search_filter,
                               self._group_attrs, limit=1)
        if not entries:
            return None
        return self._entry_to_group(entries[0])

    def get_user_groups(self, user_id: str) -> List[DirectoryGroup]:
        """Find all directory groups that contain the given user."""
        if not self._group_base:
            return []
        q = self._escape(user_id)
        member_attr = self._cfg.attr_group_member
        oc_filter = self._object_class_filter()
        # Match the member DN pattern: uid=<user_id>,<user_base_dn>
        member_dn = f"uid={q},{self._user_base}"
        search_filter = f"(&{oc_filter}({member_attr}={member_dn}))"
        logger.info("LDAP user-groups lookup: user=%s filter=%s", user_id, search_filter)
        entries = self._search(self._group_base, search_filter,
                               self._group_attrs, limit=0)
        return [self._entry_to_group(e) for e in entries]


def _first(values: list) -> str:
    if values:
        return str(values[0])
    return ""


def _dn_to_uid(dn: str) -> str:
    """Extract the first RDN value from a DN, e.g. 'uid=jdoe,ou=users,...' -> 'jdoe'."""
    if "=" not in dn:
        return dn
    return dn.split(",")[0].split("=", 1)[1]
