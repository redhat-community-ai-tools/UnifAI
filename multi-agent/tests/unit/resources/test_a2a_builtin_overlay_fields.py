"""Regression test: A2A auth fields must be configurable on built-in overlays.

``BuiltinResourceService`` (get_builtin_schema / configure_builtin /
resolve_overlay) only treats a field as part of a built-in resource's
per-identity overlay when it carries ``ReadOnlyHint(read_only=False)`` — see
``ResourceFieldEncryption.scan_schema_hints``. The MCP provider config marks
its auth fields (``sign_in``, ``bearer_token``, ...) this way; the A2A node
and provider configs must do the same for ``auth_method``, ``sign_in`` and
``bearer_token``, or a built-in A2A agent's auth-server selection and
sign-in/bearer-token flow is silently stripped out of every overlay
(``get_builtin_schema`` locks the fields as read-only, and
``configure_builtin``/``resolve_overlay`` drop them entirely).
"""
from __future__ import annotations

from mas.core.enums import ResourceCategory
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.providers.a2a_client.config import A2AProviderConfig
from mas.resources.field_encryption import ResourceFieldEncryption

REQUIRED_CONFIGURABLE_FIELDS = {"auth_method", "sign_in", "bearer_token"}


class _FakeElementRegistry:
    def __init__(self, config_cls):
        self._config_cls = config_cls

    def get_schema_json(self, category, type_key):
        return self._config_cls.model_json_schema()


def _configurable_keys(config_cls) -> set:
    fields = ResourceFieldEncryption(_FakeElementRegistry(config_cls), cipher=None)
    configurable, _sensitive = fields.scan_schema_hints(ResourceCategory.NODE.value, "irrelevant")
    return configurable


class TestA2AAgentNodeBuiltinOverlay:
    def test_auth_fields_are_configurable(self):
        configurable = _configurable_keys(A2AAgentNodeConfig)
        assert REQUIRED_CONFIGURABLE_FIELDS <= configurable

    def test_base_url_stays_admin_controlled(self):
        """base_url is the built-in resource's identity — it must stay
        read-only on the overlay; only auth should be user-configurable."""
        configurable = _configurable_keys(A2AAgentNodeConfig)
        assert "base_url" not in configurable


class TestA2AProviderBuiltinOverlay:
    def test_auth_fields_are_configurable(self):
        configurable = _configurable_keys(A2AProviderConfig)
        assert REQUIRED_CONFIGURABLE_FIELDS <= configurable

    def test_base_url_stays_admin_controlled(self):
        configurable = _configurable_keys(A2AProviderConfig)
        assert "base_url" not in configurable
