"""Schema-hint scanning and field-level encryption for resource configs.

Extracted from ``ResourcesService`` so the encryption/hint-scanning concern
has a single owner shared by both the core resource CRUD path and the
built-in overlay lifecycle (``BuiltinResourceService``), instead of being
duplicated or drifting between the two.
"""
from typing import Any, Dict, Optional, Tuple

from pydantic import BaseModel

from global_utils.utils.crypto import FieldCipher
from mas.catalog.element_registry import ElementRegistry
from mas.core.enums import ResourceCategory


class ResourceFieldEncryption:
    """Encrypts/decrypts sensitive resource-config fields at rest.

    Sensitive fields come from two sources, both honored consistently:
      - the config model's declared ``ENCRYPTED_FIELDS`` class attribute
      - fields marked ``secret`` via schema hints (``SecretHint``)

    This keeps encryption behavior identical whether a field is written via
    the base ``cfg_dict`` (create/update/create_builtin/update_builtin) or
    via a per-identity built-in overlay (``configure_builtin``).
    """

    def __init__(self, element_registry: ElementRegistry, cipher: Optional[FieldCipher]) -> None:
        self._element_registry = element_registry
        self._cipher = cipher

    def scan_schema_hints(self, category: str, type_key: str) -> Tuple[set, set]:
        """Single-pass scan of an element schema's field hints.

        Returns ``(configurable_keys, sensitive_keys)``:
        - configurable: fields with ``ReadOnlyHint(read_only=False)``
        - sensitive: fields marked ``secret``
        """
        try:
            schema = self._element_registry.get_schema_json(
                ResourceCategory(category), type_key
            )
        except KeyError:
            return set(), set()
        configurable = set()
        sensitive = set()
        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            read_only_hint = hints.get("read_only", {})
            if read_only_hint.get("read_only") is False:
                configurable.add(field_name)
            if "secret" in hints:
                sensitive.add(field_name)
        return configurable, sensitive

    def find_missing_conditionally_required_secrets(
        self,
        category: str,
        type_key: str,
        resolved_config: BaseModel,
        *,
        candidate_keys: Optional[set] = None,
        require_unconditional: bool = False,
    ) -> list[str]:
        """Secret fields that are relevant (per ``ConditionalHint``) but empty.

        Unlike ``scan_schema_hints``'s ``configurable`` set (which is only
        meaningful for built-in per-identity overlays), this needs no
        admin/overlay concept at all — it just asks "does this resolved
        config actually have the secret it claims to need?" — so it works
        identically for built-in and custom resources.

        ``candidate_keys`` restricts the scan to a caller-supplied key set
        instead of every ``secret``-hinted field in the schema — used by
        ``BuiltinResourceService.find_missing_required_overlay_fields`` to
        scope the check to configurable-and-secret fields (the only ones a
        per-identity overlay could supply). Defaults to every field
        carrying ``SecretHint`` when omitted (the plain custom-resource
        behavior).

        ``require_unconditional`` controls a candidate field with no
        ``ConditionalHint`` at all: when ``False`` (default — the custom-
        resource behavior), it's left alone, since "optional and unset" is
        a legitimate state with no schema signal saying otherwise; when
        ``True`` (the built-in overlay behavior), it's treated as always
        relevant, since being both configurable and secret already implies
        a specific caller is expected to supply it.

        Without this check, an empty credential just gets handed to the
        element's validator, which may probe the connection anyway and —
        if the server happens to tolerate unauthenticated requests —
        incorrectly report the resource as valid.
        """
        try:
            schema = self._element_registry.get_schema_json(
                ResourceCategory(category), type_key
            )
        except KeyError:
            return []

        properties = schema.get("properties", {})
        keys = sorted(candidate_keys) if candidate_keys is not None else sorted(properties)

        missing = []
        for key in keys:
            hints = properties.get(key, {}).get("hints", {})
            if candidate_keys is None and "secret" not in hints:
                continue
            conditional = hints.get("conditional", {}).get("visible_when")
            if conditional:
                if not all(
                    getattr(resolved_config, field_name, None) == value
                    for field_name, value in conditional.items()
                ):
                    continue
            elif not require_unconditional:
                continue
            if not getattr(resolved_config, key, None):
                missing.append(key)
        return missing

    def encrypt_fields(
        self,
        cfg_dict: dict,
        model_cls: type,
        category: Optional[str] = None,
        type_key: Optional[str] = None,
    ) -> dict:
        """Encrypt sensitive fields before storage.

        Combines the config's declared ``ENCRYPTED_FIELDS`` with any fields
        marked ``secret`` via schema hints (``SecretHint``). Both sources are
        honored so a field only needs one annotation — a schema-hint-only
        field (e.g. an MCP ``bearer_token``, which has no ``ENCRYPTED_FIELDS``
        entry) is still encrypted at rest, keeping base ``cfg_dict`` storage
        consistent with the encryption applied to per-user overlays.
        """
        if not self._cipher:
            return cfg_dict
        sensitive = set(getattr(model_cls, "ENCRYPTED_FIELDS", ()))
        if category and type_key:
            _, hint_sensitive = self.scan_schema_hints(category, type_key)
            sensitive |= hint_sensitive
        for field in sensitive:
            if cfg_dict.get(field):
                cfg_dict[field] = self._cipher.encrypt(str(cfg_dict[field]))
        return cfg_dict

    @staticmethod
    def _effective_sensitive_keys(sensitive_keys: set, model_cls: Optional[type]) -> set:
        """Union schema-hint-derived ``sensitive_keys`` with a model's declared ``ENCRYPTED_FIELDS``.

        Shared by ``encrypt_config_fields`` and ``decrypt_config_fields`` so both
        honor the same two sources — keeping per-identity overlay
        encryption/decryption consistent with base ``cfg_dict`` encryption
        (see ``encrypt_fields``).
        """
        if model_cls is None:
            return sensitive_keys
        return sensitive_keys | set(getattr(model_cls, "ENCRYPTED_FIELDS", ()))

    def encrypt_config_fields(
        self,
        config: Dict[str, Any],
        sensitive_keys: set,
        model_cls: Optional[type] = None,
    ) -> Dict[str, Any]:
        """Encrypt values of fields identified as sensitive."""
        if not self._cipher:
            return config
        sensitive_keys = self._effective_sensitive_keys(sensitive_keys, model_cls)
        result = {}
        for k, v in config.items():
            if k in sensitive_keys and v:
                result[k] = self._cipher.encrypt(str(v))
            else:
                result[k] = v
        return result

    def decrypt_config_fields(
        self,
        config: Dict[str, Any],
        sensitive_keys: set,
        model_cls: Optional[type] = None,
    ) -> Dict[str, Any]:
        """Decrypt values of fields identified as sensitive.

        See ``encrypt_config_fields`` for why ``model_cls`` is unioned in —
        decryption must recognize the same field set that encryption used.
        """
        if not self._cipher:
            return config
        sensitive_keys = self._effective_sensitive_keys(sensitive_keys, model_cls)
        result = {}
        for k, v in config.items():
            if k in sensitive_keys and v and isinstance(v, str):
                result[k] = self._cipher.decrypt(v)
            else:
                result[k] = v
        return result
