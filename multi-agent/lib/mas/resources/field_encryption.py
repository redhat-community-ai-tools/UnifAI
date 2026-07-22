"""Schema-hint scanning and field-level encryption for resource configs.

Extracted from ``ResourcesService`` so the encryption/hint-scanning concern
has a single owner shared by both the core resource CRUD path and the
built-in overlay lifecycle (``BuiltinResourceService``), instead of being
duplicated or drifting between the two.
"""
from typing import Any, Dict, Optional, Tuple

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
                cfg_dict[field] = self._cipher.encrypt(cfg_dict[field])
        return cfg_dict

    def encrypt_config_fields(
        self,
        config: Dict[str, Any],
        sensitive_keys: set,
        model_cls: Optional[type] = None,
    ) -> Dict[str, Any]:
        """Encrypt values of fields identified as sensitive.

        Unions schema-hint-derived ``sensitive_keys`` with the config model's
        declared ``ENCRYPTED_FIELDS`` (when ``model_cls`` is provided), the
        same two sources honored by ``encrypt_fields`` — keeping per-identity
        overlay encryption consistent with base ``cfg_dict`` encryption.
        """
        if not self._cipher:
            return config
        if model_cls is not None:
            sensitive_keys = sensitive_keys | set(getattr(model_cls, "ENCRYPTED_FIELDS", ()))
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
        if model_cls is not None:
            sensitive_keys = sensitive_keys | set(getattr(model_cls, "ENCRYPTED_FIELDS", ()))
        result = {}
        for k, v in config.items():
            if k in sensitive_keys and v and isinstance(v, str):
                result[k] = self._cipher.decrypt(v)
            else:
                result[k] = v
        return result
