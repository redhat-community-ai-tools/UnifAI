"""Unit tests for ResourcesService/BuiltinResourceService covering the
security/correctness fixes:

- IDOR guard on update/delete (guard_write_access)
- Draft-builtin visibility enforcement (get_visible / validate_resource / get_cards)
- Secret encryption consistency (schema-hint-only secrets)
- resolve() decrypting cfg_dict while merging the builtin overlay
- configure_builtin() failing loudly when no repo is configured

Generic CRUD/visibility/validation behavior is exercised on ``service``
(``ResourcesService``); the built-in admin/overlay lifecycle
(create/promote/demote/configure/schema) is exercised directly on
``builtin_service`` (``BuiltinResourceService``), which is the sole owner
of that concept now — see ``resources.md``. Both fixtures share the same
underlying fake stores (see ``conftest.py``), so state mutated through one
is visible through the other within a test.
"""
from unittest.mock import Mock

import pytest

from mas.collaboration.models import TeamEditLockHolder
from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceCategory, ResourceVisibility
from mas.core.identity import Identity
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceLockedError,
    BuiltinConfigUnavailableError,
    BuiltinDependentsPublicError,
)
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import CoreResourceService
from mas.resources.builtin_aware_service import BuiltinAwareResourceService
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.builtin_models import BuiltinUpdateRequest, identity_to_key

from global_utils.utils.crypto import FieldCipher

from tests.unit.resources.conftest import FAKE_CATEGORY, FAKE_TYPE, TEST_ENCRYPTION_KEY


# ────────────────────────────── helpers ──────────────────────────────

def _make_custom_resource(service, identity, name="custom-1", bearer_token=None) -> Resource:
    return service.create(
        identity=identity,
        category=FAKE_CATEGORY,
        type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://a.example"},
    )


def _make_builtin_resource(
    builtin_service, admin_identity, name="builtin-1", available_to_all=True, bearer_token="s3cr3t",
) -> Resource:
    resource, _ = builtin_service.create_builtin_with_cascade(
        identity=admin_identity,
        category=FAKE_CATEGORY,
        resource_type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://b.example"},
        available_to_all=available_to_all,
    )
    return resource


def _make_disabled_category_resource(service, identity, name="my-retriever") -> Resource:
    """A resource in a category that can never become a built-in
    (``ResourceCategory.RETRIEVER``), created by writing straight to the
    store since ``service.create()`` would need a registered schema for it."""
    doc = Resource(
        identity=identity,
        category=ResourceCategory.RETRIEVER,
        type="fake_retriever",
        name=name,
        cfg_dict={},
    )
    return service._store.create(doc)


def _link_nested(service, parent: Resource, *child_rids: str) -> Resource:
    """Wire ``parent.nested_refs`` directly, bypassing schema Ref-field
    extraction, so tests can build an aggregator/leaf graph (e.g. an agent
    referencing an LLM/provider/tool) without a real Ref-typed fake schema."""
    doc = service.get(parent.rid)
    doc.nested_refs = list(child_rids)
    return service._store.update(doc)


# ────────────────────────────── IDOR guard ──────────────────────────────

class TestGuardWriteAccess:
    def test_owner_may_write_own_custom_resource(self, service, alice):
        doc = _make_custom_resource(service, alice)
        resolved = service.guard_write_access(doc.rid, CallerScope(identity=alice, is_admin=False))
        assert resolved.rid == doc.rid

    def test_other_user_is_denied_on_custom_resource(self, service, alice, bob):
        """Regression test for the IDOR: a different user must not be able
        to pass the write guard for someone else's custom resource."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(ResourceAccessDeniedError):
            service.guard_write_access(doc.rid, CallerScope(identity=bob, is_admin=False))

    def test_admin_bypasses_ownership_check(self, service, alice, admin_identity):
        doc = _make_custom_resource(service, alice)
        resolved = service.guard_write_access(doc.rid, CallerScope(identity=admin_identity, is_admin=True))
        assert resolved.rid == doc.rid

    def test_builtin_resource_blocked_for_non_admin_even_if_owner(self, service, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity)
        with pytest.raises(BuiltInWriteProtectedError):
            service.guard_write_access(doc.rid, CallerScope(identity=admin_identity, is_admin=False))

    def test_team_identity_ownership_matches_by_type_and_id(self, service):
        team = Identity.team("team-a")
        doc = _make_custom_resource(service, team)
        # Same team id, different display_name still matches.
        other_ref = Identity.team("team-a", display_name="Renamed Team")
        resolved = service.guard_write_access(doc.rid, CallerScope(identity=other_ref, is_admin=False))
        assert resolved.rid == doc.rid

        different_team = Identity.team("team-b")
        with pytest.raises(ResourceAccessDeniedError):
            service.guard_write_access(doc.rid, CallerScope(identity=different_team, is_admin=False))


class TestGuardWriteAccessAdminLock:
    """The admin edit lock check is now part of ``guard_write_access`` —
    an admin mutating a built-in resource must be rejected with
    ``ResourceLockedError`` if another admin holds the cooperative lock."""

    @pytest.fixture
    def lock_reader(self) -> Mock:
        return Mock()

    @pytest.fixture
    def service_with_lock(
        self,
        resource_registry: ResourcesRegistry,
        element_registry: "FakeElementRegistry",
        builtin_user_config_repo: "FakeBuiltinUserConfigRepository",
        builtin_resource_descriptor_repo: "FakeBuiltinResourceDescriptorRepository",
        lock_reader: Mock,
    ) -> BuiltinAwareResourceService:
        field_encryption = ResourceFieldEncryption(element_registry, FieldCipher(TEST_ENCRYPTION_KEY))
        core = CoreResourceService(
            resource_registry=resource_registry,
            element_registry=element_registry,
            field_encryption=field_encryption,
        )
        return BuiltinAwareResourceService(
            core,
            descriptor_repo=builtin_resource_descriptor_repo,
            builtin_user_config_repo=builtin_user_config_repo,
            admin_lock_reader=lock_reader,
        )

    def test_admin_blocked_when_builtin_locked_by_another(
        self, service_with_lock, lock_reader, builtin_service, admin_identity,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity)
        lock_reader.get_admin_edit_lock.return_value = TeamEditLockHolder(
            user_id="other-admin", display_name="Other Admin",
        )

        with pytest.raises(ResourceLockedError) as exc_info:
            service_with_lock.guard_write_access(
                doc.rid, CallerScope(identity=admin_identity, is_admin=True),
                username="admin",
            )
        assert exc_info.value.locked_by_user_id == "other-admin"

    def test_admin_allowed_when_builtin_locked_by_self(
        self, service_with_lock, lock_reader, builtin_service, admin_identity,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity)
        lock_reader.get_admin_edit_lock.return_value = TeamEditLockHolder(
            user_id="admin", display_name="Admin",
        )

        resolved = service_with_lock.guard_write_access(
            doc.rid, CallerScope(identity=admin_identity, is_admin=True),
            username="admin",
        )
        assert resolved.rid == doc.rid

    def test_admin_allowed_when_no_lock_held(
        self, service_with_lock, lock_reader, builtin_service, admin_identity,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity)
        lock_reader.get_admin_edit_lock.return_value = None

        resolved = service_with_lock.guard_write_access(
            doc.rid, CallerScope(identity=admin_identity, is_admin=True),
            username="admin",
        )
        assert resolved.rid == doc.rid

    def test_custom_resource_skips_lock_check(
        self, service_with_lock, lock_reader, admin_identity,
    ):
        doc = _make_custom_resource(service_with_lock, admin_identity)

        service_with_lock.guard_write_access(
            doc.rid, CallerScope(identity=admin_identity, is_admin=True),
            username="admin",
        )
        lock_reader.get_admin_edit_lock.assert_not_called()

    def test_no_lock_reader_skips_lock_check(
        self, service, builtin_service, admin_identity,
    ):
        """When ``admin_lock_reader`` is None (Redis not configured), the
        lock check is a no-op — admins can always mutate built-ins."""
        doc = _make_builtin_resource(builtin_service, admin_identity)
        resolved = service.guard_write_access(
            doc.rid, CallerScope(identity=admin_identity, is_admin=True),
            username="admin",
        )
        assert resolved.rid == doc.rid


# ────────────────────────────── visibility guards ──────────────────────────────

class TestVisibilityGuards:
    def test_get_visible_blocks_draft_builtin_for_non_admin(self, service, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.get_visible(doc.rid, caller=CallerScope(is_admin=False))

    def test_get_visible_allows_draft_builtin_for_admin(self, service, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=False)
        resolved = service.get_visible(doc.rid, caller=CallerScope(is_admin=True))
        assert resolved.rid == doc.rid

    def test_get_visible_allows_public_builtin_for_anyone(self, service, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=True)
        resolved = service.get_visible(doc.rid, caller=CallerScope(is_admin=False))
        assert resolved.rid == doc.rid

    def test_validate_resource_blocks_probing_draft_builtins(self, service, builtin_service, admin_identity, alice):
        """Regression test: validate_resource must not let a non-admin probe
        a draft built-in's existence/schema via the validation endpoint."""
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.validate_resource(doc.rid, CallerScope(identity=alice, is_admin=False))

    def test_get_cards_blocks_draft_builtin_for_non_admin(self, service, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.get_cards([doc.rid], caller=CallerScope(is_admin=False))

    def test_validate_resource_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: validate_resource must forward ``caller.identity``
        into ``get_visible`` so a non-owner cannot validate someone else's
        custom resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(KeyError):
            service.validate_resource(doc.rid, CallerScope(identity=bob, is_admin=False))

    def test_get_cards_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: get_cards must forward ``caller.identity`` into
        ``get_visible`` so a non-owner cannot build a card for someone
        else's custom resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(KeyError):
            service.get_cards([doc.rid], caller=CallerScope(identity=bob, is_admin=False))

    def test_resolve_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: resolve() must forward ``caller.identity`` into
        ``get_visible`` so a non-owner cannot resolve/decrypt someone
        else's custom resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice, bearer_token="alices-secret")
        with pytest.raises(KeyError):
            service.resolve(doc.rid, CallerScope(identity=bob, is_admin=False))


# ────────────────────────────── encryption ──────────────────────────────

class TestEncryption:
    def test_create_builtin_encrypts_schema_hint_only_secret_field(self, service, builtin_service, admin_identity):
        """bearer_token has no ENCRYPTED_FIELDS entry on the fake config class
        (mirroring the real McpProviderConfig) — it is only marked via
        SecretHint. The base cfg_dict must still be encrypted at rest."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="super-secret")

        raw = service.get(doc.rid)
        stored = raw.cfg_dict["bearer_token"]
        assert stored != "super-secret"
        # Behavior, not representation: it must be decryptable back to the
        # original secret via the same cipher used elsewhere (also exercised
        # end-to-end by test_resolve_decrypts_cfg_dict below).
        assert service._fields._cipher.decrypt(stored) == "super-secret"

    def test_resolve_decrypts_cfg_dict(self, service, builtin_service, admin_identity):
        """Regression test: resolve() must return plaintext secrets to
        downstream elements, not ciphertext."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="super-secret")

        resolved_config = service.resolve(doc.rid)
        assert resolved_config.bearer_token == "super-secret"


# ────────────────────────────── builtin overlay ──────────────────────────────

class TestBuiltinOverlay:
    def test_configure_builtin_raises_when_repo_unavailable(
        self, builtin_service_without_config_repo, admin_identity, alice,
    ):
        doc = _make_builtin_resource(builtin_service_without_config_repo, admin_identity)
        with pytest.raises(BuiltinConfigUnavailableError):
            builtin_service_without_config_repo.configure_builtin(
                doc.rid, identity=alice, config={"bearer_token": "mine"},
            )

    def test_configure_builtin_rejects_invalid_field_type(self, builtin_service, admin_identity, alice):
        """An overlay value that fails Pydantic validation against the
        element's config model must be rejected at configure-time, not
        silently persisted and only discovered later at resolve()."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        with pytest.raises(ValueError):
            builtin_service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": 12345})

        # Nothing should have been persisted from the rejected attempt.
        assert builtin_service.get_user_config(doc.rid, identity=alice) is None

    def test_configure_builtin_round_trips_through_get_user_config(self, builtin_service, admin_identity, alice):
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")

        builtin_service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        user_config = builtin_service.get_user_config(doc.rid, identity=alice)
        assert user_config["bearer_token"] == "alices-secret"

    def test_configure_builtin_auth_metadata_round_trips_through_get_user_config(
        self, builtin_service, admin_identity, alice,
    ):
        """Regression test: `server_identifier`/`scheme_type` (hidden,
        non-user-configurable) are written to the identity's overlay by
        `configure_builtin()` right after a sign-in flow resolves the real
        auth server — but `get_user_config()` used to filter the overlay
        down to `configurable_keys` only, silently dropping them from what
        the UI sees. Without them, hidden validations for an
        already-signed-in user would keep falling back to an
        unauthenticated probe against a stale/empty identifier."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")

        builtin_service.configure_builtin(
            doc.rid, identity=alice, config={"server_identifier": "https://issuer.example"},
        )

        user_config = builtin_service.get_user_config(doc.rid, identity=alice)
        assert user_config["server_identifier"] == "https://issuer.example"

    def test_to_dict_merges_overlay_tool_names_for_inventory_card(
        self, service, builtin_service, admin_identity, alice,
    ):
        """Regression test: inventory cards read ``cfg_dict`` from list/configure
        serialization. Without merging the caller's overlay, a user-selected
        ``tool_names`` list never reaches the card and the schema's
        ``empty_text`` ("All tools") is shown instead."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        builtin_service.configure_builtin(
            doc.rid, identity=alice, config={"tool_names": ["search", "fetch"]},
        )

        serialized = service.to_dict(doc, identity=alice)
        assert serialized["cfg_dict"]["tool_names"] == ["search", "fetch"]
        assert serialized["user_configured"] is True

        # Without identity, keep the shared base (empty tool_names).
        base_serialized = service.to_dict(doc)
        assert base_serialized["cfg_dict"].get("tool_names") in (None, [])

    def test_configure_builtin_overlay_takes_priority_in_resolve(
        self, service, builtin_service, admin_identity, alice, bob,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        builtin_service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        resolved_for_alice = service.resolve(doc.rid, CallerScope(identity=alice))
        resolved_for_bob = service.resolve(doc.rid, CallerScope(identity=bob))
        resolved_no_identity = service.resolve(doc.rid, CallerScope(identity=None))

        assert resolved_for_alice.bearer_token == "alices-secret"
        # Bob never configured his own overlay — he must NOT silently inherit
        # the admin's base-config secret (see `strip_unconfigured_secrets`).
        assert resolved_for_bob.bearer_token is None
        # identity=None (schema-only tooling) intentionally skips overlay
        # resolution entirely and keeps returning raw built-in defaults —
        # this is the documented, backward-compatible no-caller-identity path.
        assert resolved_no_identity.bearer_token == "default-secret"

    def test_resolve_strips_unconfigured_secret_even_without_any_overlays(
        self, service, builtin_service, admin_identity, alice,
    ):
        """Regression test: a per-user secret field baked into a built-in's
        shared base config (e.g. an admin's own bearer token, saved while
        testing connectivity before promoting it) must never leak to a user
        who has no overlay of their own — even when *nobody* has configured
        one yet."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="admins-own-secret")

        resolved = service.resolve(doc.rid, CallerScope(identity=alice))

        assert resolved.bearer_token is None

    def test_configure_builtin_encrypts_encrypted_fields_only_secret(self, builtin_service, admin_identity, alice):
        """``api_key`` is sensitive only via ``ENCRYPTED_FIELDS`` (no
        ``SecretHint``, like some real element configs). Regression test:
        the per-identity overlay must encrypt it at rest just like the base
        ``cfg_dict`` does via ``encrypt_fields``, not silently store it in
        plaintext because schema-hint scanning alone doesn't see it."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")

        builtin_service.configure_builtin(doc.rid, identity=alice, config={"api_key": "alices-api-key"})

        stored = builtin_service._builtin_user_config_repo.get(doc.rid, identity_to_key(alice))
        assert stored.fields["api_key"] != "alices-api-key"

        user_config = builtin_service.get_user_config(doc.rid, identity=alice)
        assert user_config["api_key"] == "alices-api-key"

    def test_get_cards_passes_identity_through_for_overlay(self, service, builtin_service, admin_identity, alice):
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        builtin_service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        captured = {}

        def fake_build_all_cards(configs):
            captured["configs"] = configs
            return {c.rid: c for c in configs}

        service._card_service.build_all_cards.side_effect = fake_build_all_cards

        service.get_cards([doc.rid], caller=CallerScope(identity=alice, is_admin=False))

        built = captured["configs"][0]
        assert built.config.bearer_token == "alices-secret"


# ────────────────────────────── required-secret validation gate ──────────────────────────────

class TestBuiltinRequiredSecretValidation:
    """A built-in resource with a per-user secret field (e.g. an MCP bearer
    token) must not validate as "working" for a caller who never configured
    their own overlay — even if the element's real validator would have
    (perhaps accidentally) succeeded against an unauthenticated value. See
    ``BuiltinResourceService.find_missing_required_overlay_fields``."""

    @staticmethod
    def _capture_ordered_configs(service, is_valid: bool):
        captured = {}

        def fake_validate_ordered(configs, context):
            captured["configs"] = configs
            return {c.rid: Mock(is_valid=is_valid) for c in configs}

        service._validation_service.validate_ordered.side_effect = fake_validate_ordered
        return captured

    def test_validate_resource_flags_missing_secret_for_caller_without_overlay(
        self, service, builtin_service, admin_identity, bob,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        captured = self._capture_ordered_configs(service, is_valid=False)

        service.validate_resource(doc.rid, CallerScope(identity=bob))

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is not None
        assert "bearer_token" in built.validation_override_error

    def test_validate_resource_does_not_flag_when_caller_has_overlay(
        self, service, builtin_service, admin_identity, alice,
    ):
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        builtin_service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, CallerScope(identity=alice))

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None

    def test_validate_resource_not_flagged_without_identity(
        self, service, builtin_service, admin_identity,
    ):
        """``caller.identity=None`` (schema-only tooling) skips the overlay
        concept entirely, same as ``resolve()`` — it must not be flagged
        either."""
        doc = _make_builtin_resource(builtin_service, admin_identity, bearer_token="default-secret")
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, CallerScope(identity=None))

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None

    def test_custom_resource_is_never_flagged(self, service, alice):
        """The gate only applies to built-ins — a custom resource's own
        (possibly empty) secret field is the caller's own business, not a
        missing-overlay situation."""
        doc = _make_custom_resource(service, alice, bearer_token=None)
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, CallerScope(identity=alice))

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None


# ────────────────────────────── card-visibility hint ──────────────────────────────

class TestCardVisibilityHint:
    """``CardHint`` (``hints.card``) must survive schema serialization
    end-to-end through ``get_builtin_schema()`` — the same JSON schema
    consumers use to know which fields to render on inventory cards for
    built-in vs. custom elements."""

    def test_card_hint_present_on_builtin_schema(self, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity)
        schema = builtin_service.get_builtin_schema(doc.rid, is_admin=True)

        endpoint_hints = schema["properties"]["endpoint"]["hints"]
        assert endpoint_hints["card"] == {"contexts": ["custom"]}

    def test_card_hint_untouched_by_read_only_annotation(self, builtin_service, admin_identity):
        """``get_builtin_schema`` adds ``read_only`` hints to non-configurable
        fields but must not strip or overwrite any pre-existing ``card`` hint
        while doing so."""
        doc = _make_builtin_resource(builtin_service, admin_identity)
        schema = builtin_service.get_builtin_schema(doc.rid, is_admin=True)

        endpoint_hints = schema["properties"]["endpoint"]["hints"]
        # `endpoint` has no ReadOnlyHint(read_only=False), so it becomes
        # locked for built-ins — but its `card` hint must still be intact.
        assert endpoint_hints["read_only"] == {"read_only": True}
        assert endpoint_hints["card"] == {"contexts": ["custom"]}


# ────────────────────────────── promote/demote lifecycle ──────────────────────────────

class TestPromoteDemote:
    def test_promote_custom_to_public_builtin(self, service, builtin_service, alice):
        doc = _make_custom_resource(service, alice)
        promoted, _ = builtin_service.promote_with_cascade(doc.rid)
        assert builtin_service.is_builtin(promoted.rid)
        assert builtin_service.get_descriptor(promoted.rid).visibility == ResourceVisibility.PUBLIC

    def test_demote_sets_draft_visibility(self, builtin_service, admin_identity):
        doc = _make_builtin_resource(builtin_service, admin_identity, available_to_all=True)
        demoted = builtin_service.demote(doc.rid)
        assert builtin_service.get_descriptor(demoted.rid).visibility == ResourceVisibility.DRAFT

    def test_toggle_visibility_delegates_to_promote_and_demote(self, service, builtin_service, alice, admin_identity):
        custom = _make_custom_resource(service, alice)
        toggled_on, _ = builtin_service.toggle_visibility_with_cascade(custom.rid, available_to_all=True)
        assert builtin_service.get_descriptor(toggled_on.rid).visibility == ResourceVisibility.PUBLIC
        assert builtin_service.is_builtin(toggled_on.rid)

        toggled_off, _ = builtin_service.toggle_visibility_with_cascade(toggled_on.rid, available_to_all=False)
        assert builtin_service.get_descriptor(toggled_off.rid).visibility == ResourceVisibility.DRAFT


# ────────────────────────────── nested-dependency cascade ──────────────────────────────

class TestNestedDependencyCascade:
    """An agent/node can aggregate leaf elements (LLMs, providers, tools)
    via ``nested_refs``. Promoting the agent to "available to all" must
    cascade to those leaves, and demoting a leaf that a public agent still
    uses must be blocked."""

    def test_promote_cascades_to_not_yet_public_nested_refs(self, service, builtin_service, alice, admin_identity):
        llm = _make_custom_resource(service, alice, name="my-llm")
        agent = _make_custom_resource(service, alice, name="my-agent")
        _link_nested(service, agent, llm.rid)

        builtin_service.promote_with_cascade(agent.rid)

        assert builtin_service.is_builtin(llm.rid)
        assert builtin_service.get_descriptor(llm.rid).visibility == ResourceVisibility.PUBLIC

    def test_promote_cascades_transitively_through_a_chain(self, service, builtin_service, alice):
        provider = _make_custom_resource(service, alice, name="my-provider")
        tool = _make_custom_resource(service, alice, name="my-tool")
        agent = _make_custom_resource(service, alice, name="my-agent-2")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)

        builtin_service.promote_with_cascade(agent.rid)

        assert builtin_service.get_descriptor(tool.rid).visibility == ResourceVisibility.PUBLIC
        assert builtin_service.get_descriptor(provider.rid).visibility == ResourceVisibility.PUBLIC

    def test_promote_does_not_touch_already_public_nested_refs(self, service, builtin_service, alice, admin_identity):
        llm = _make_builtin_resource(builtin_service, admin_identity, name="shared-llm", available_to_all=True)
        agent = _make_custom_resource(service, alice, name="agent-using-shared-llm")
        _link_nested(service, agent, llm.rid)

        builtin_service.promote_with_cascade(agent.rid)

        # No-op: still public, version unchanged by the cascade.
        assert service.get(llm.rid).version == llm.version

    def test_preview_cascade_targets_lists_not_yet_public_deps(self, service, builtin_service, alice):
        llm = _make_custom_resource(service, alice, name="preview-llm")
        agent = _make_custom_resource(service, alice, name="preview-agent")
        _link_nested(service, agent, llm.rid)

        targets = builtin_service.preview_cascade_targets(agent.rid)

        assert [t.rid for t in targets] == [llm.rid]

    def test_demote_blocked_when_public_agent_still_uses_it(self, service, builtin_service, alice):
        llm = _make_custom_resource(service, alice, name="blocked-llm")
        agent = _make_custom_resource(service, alice, name="blocking-agent")
        _link_nested(service, agent, llm.rid)
        builtin_service.promote_with_cascade(agent.rid)  # cascades llm to public too

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            builtin_service.demote(llm.rid)

        assert "blocking-agent" in str(exc_info.value)
        assert [d.rid for d in exc_info.value.dependents] == [agent.rid]

    def test_demote_allowed_once_dependent_agent_is_demoted(self, service, builtin_service, alice):
        llm = _make_custom_resource(service, alice, name="unblocked-llm")
        agent = _make_custom_resource(service, alice, name="unblocking-agent")
        _link_nested(service, agent, llm.rid)
        builtin_service.promote_with_cascade(agent.rid)

        builtin_service.demote(agent.rid)
        demoted_llm = builtin_service.demote(llm.rid)

        assert builtin_service.get_descriptor(demoted_llm.rid).visibility == ResourceVisibility.DRAFT

    def test_demote_blocked_transitively_through_a_chain(self, service, builtin_service, alice):
        provider = _make_custom_resource(service, alice, name="chain-provider")
        tool = _make_custom_resource(service, alice, name="chain-tool")
        agent = _make_custom_resource(service, alice, name="chain-agent")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)
        builtin_service.promote_with_cascade(agent.rid)  # cascades tool + provider to public

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            builtin_service.demote(provider.rid)

        assert {d.rid for d in exc_info.value.dependents} == {tool.rid, agent.rid}

    def test_demote_not_blocked_by_unrelated_draft_agent(self, service, builtin_service, alice):
        llm = _make_custom_resource(service, alice, name="free-llm")
        draft_agent = _make_custom_resource(service, alice, name="draft-agent")
        _link_nested(service, draft_agent, llm.rid)
        builtin_service.promote_with_cascade(llm.rid)  # llm becomes public on its own; agent stays custom/draft

        demoted = builtin_service.demote(llm.rid)
        assert builtin_service.get_descriptor(demoted.rid).visibility == ResourceVisibility.DRAFT

    def test_promote_rejects_cascade_through_disabled_category_dependency(self, service, builtin_service, alice):
        """Regression test: a dependency in a `builtin_disabled_categories()`
        category (e.g. a retriever) must reject the whole promotion instead
        of being silently skipped — leaving the parent public while it still
        references a resource that end users can never see would defeat the
        entire cascade-promotion guarantee."""
        retriever = _make_disabled_category_resource(service, alice)
        agent = _make_custom_resource(service, alice, name="agent-with-retriever-dep")
        _link_nested(service, agent, retriever.rid)

        with pytest.raises(ValueError, match="is not supported as a built-in resource"):
            builtin_service.promote_with_cascade(agent.rid)

        # The whole promotion is rejected before any mutation happens — the
        # agent and its retriever dependency never become built-ins.
        assert builtin_service.get_descriptor(agent.rid) is None
        assert builtin_service.get_descriptor(retriever.rid) is None

    def test_update_builtin_rejects_cascade_through_disabled_category_dependency(
        self, service, builtin_service, alice, admin_identity,
    ):
        """Same guarantee via `update_builtin_with_cascade` (toggling an
        existing draft built-in to "available to all"): no public resource
        should ever be published if a dependency can't cascade."""
        retriever = _make_disabled_category_resource(service, alice)
        builtin_doc = _make_builtin_resource(
            builtin_service, admin_identity, name="draft-builtin-with-retriever-dep",
            available_to_all=False,
        )
        _link_nested(service, builtin_doc, retriever.rid)

        with pytest.raises(ValueError, match="is not supported as a built-in resource"):
            builtin_service.update_builtin_with_cascade(
                builtin_doc.rid, update=BuiltinUpdateRequest(available_to_all=True),
            )

        assert builtin_service.get_descriptor(builtin_doc.rid).visibility == ResourceVisibility.DRAFT
        assert builtin_service.get_descriptor(retriever.rid) is None

    def test_promote_parent_stays_draft_when_cascade_fails_midway(
        self, service, builtin_service, builtin_resource_descriptor_repo, alice,
    ):
        """Regression: if `_cascade_promote_dependencies` raises mid-loop
        (e.g. a Mongo write error on the second dependency), the parent must
        NOT end up PUBLIC while a dependency remains non-built-in — that
        would break the cascade invariant."""
        llm = _make_custom_resource(service, alice, name="cascade-fail-llm")
        tool = _make_custom_resource(service, alice, name="cascade-fail-tool")
        agent = _make_custom_resource(service, alice, name="cascade-fail-agent")
        _link_nested(service, agent, llm.rid, tool.rid)

        original_save = builtin_resource_descriptor_repo.save
        call_count = {"n": 0}

        def failing_save(descriptor):
            call_count["n"] += 1
            # Let the parent's intermediate DRAFT save through, then fail on
            # the first dependency's descriptor write inside the cascade loop.
            if descriptor.rid in (llm.rid, tool.rid) and descriptor.visibility == ResourceVisibility.PUBLIC:
                raise RuntimeError("simulated Mongo write error")
            return original_save(descriptor)

        builtin_service._descriptor_repo.save = failing_save

        with pytest.raises(RuntimeError, match="simulated Mongo write error"):
            builtin_service.promote_with_cascade(agent.rid)

        # The parent already became a (draft) built-in before the cascade
        # ran, and that intermediate state survives the failed cascade.
        assert builtin_service.get_descriptor(agent.rid).visibility == ResourceVisibility.DRAFT

        # Neither dependency was ever actually promoted (the failing write
        # is never persisted).
        assert builtin_service.get_descriptor(llm.rid) is None
        assert builtin_service.get_descriptor(tool.rid) is None
