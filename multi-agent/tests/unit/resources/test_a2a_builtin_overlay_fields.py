"""Regression test: A2A auth fields must be configurable on built-in overlays.

``BuiltinResourceService`` (get_builtin_schema / configure_builtin /
resolve_overlay) only treats a field as part of a built-in resource's
per-identity overlay when it carries ``ReadOnlyHint(read_only=False)`` — see
``ResourceFieldEncryption.scan_schema_hints``. The MCP provider config marks
its credential fields (``sign_in``, ``bearer_token``) this way while leaving
``auth_method`` unannotated (admin-controlled — it decides *how* every caller
of a shared built-in authenticates, not something each user picks for
themselves). The A2A node and provider configs must mirror this split, or a
built-in A2A agent's sign-in/bearer-token flow is silently stripped out of
every overlay (``get_builtin_schema`` locks the fields as read-only, and
``configure_builtin``/``resolve_overlay`` drop them entirely) — or, in the
other direction, callers would each be able to override the admin's chosen
auth method for a shared resource.
"""
from __future__ import annotations

from mas.core.enums import ResourceCategory
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.providers.a2a_client.config import A2AProviderConfig
from mas.resources.field_encryption import ResourceFieldEncryption

REQUIRED_CONFIGURABLE_FIELDS = {"sign_in", "bearer_token"}
ADMIN_CONTROLLED_FIELDS = {"base_url", "auth_method"}


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

    def test_admin_controlled_fields_stay_locked(self):
        """base_url is the built-in resource's identity and auth_method is
        the admin's choice of *how* callers authenticate — both must stay
        read-only on the overlay; only the caller's own credentials
        (sign_in / bearer_token) are user-configurable."""
        configurable = _configurable_keys(A2AAgentNodeConfig)
        assert ADMIN_CONTROLLED_FIELDS.isdisjoint(configurable)


class TestA2AProviderBuiltinOverlay:
    def test_auth_fields_are_configurable(self):
        configurable = _configurable_keys(A2AProviderConfig)
        assert REQUIRED_CONFIGURABLE_FIELDS <= configurable

    def test_admin_controlled_fields_stay_locked(self):
        configurable = _configurable_keys(A2AProviderConfig)
        assert ADMIN_CONTROLLED_FIELDS.isdisjoint(configurable)
