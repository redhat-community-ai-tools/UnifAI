"""Unit tests for ResourcesService covering the security/correctness fixes:

- IDOR guard on update/delete (guard_write_access)
- Draft-builtin visibility enforcement (get_visible / validate_resource / get_cards)
- Secret encryption consistency (schema-hint-only secrets)
- resolve() decrypting cfg_dict while merging the builtin overlay
- configure_builtin() failing loudly when no repo is configured
"""
from unittest.mock import Mock

import pytest

from mas.core.enums import ResourceOwnership, ResourceVisibility
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    BuiltinConfigUnavailableError,
    BuiltinDependentsPublicError,
)
from mas.resources.models import Resource
from mas.resources.builtin_models import identity_to_key

from tests.unit.resources.conftest import FAKE_CATEGORY, FAKE_TYPE


# ────────────────────────────── helpers ──────────────────────────────

def _make_custom_resource(service, identity, name="custom-1", bearer_token=None) -> Resource:
    return service.create(
        identity=identity,
        category=FAKE_CATEGORY,
        type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://a.example"},
    )


def _make_builtin_resource(service, admin_identity, name="builtin-1", available_to_all=True, bearer_token="s3cr3t") -> Resource:
    resource, _ = service.create_builtin_with_cascade(
        identity=admin_identity,
        category=FAKE_CATEGORY,
        type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://b.example"},
        available_to_all=available_to_all,
    )
    return resource


def _make_disabled_category_resource(service, identity, name="my-retriever") -> Resource:
    """A resource in a category that can never become a built-in
    (``ResourceCategory.RETRIEVER``), created by writing straight to the
    store since ``service.create()`` would need a registered schema for it."""
    from mas.core.enums import ResourceCategory as _ResourceCategory

    doc = Resource(
        identity=identity,
        category=_ResourceCategory.RETRIEVER,
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
        resolved = service.guard_write_access(doc.rid, identity=alice, is_admin=False)
        assert resolved.rid == doc.rid

    def test_other_user_is_denied_on_custom_resource(self, service, alice, bob):
        """Regression test for the IDOR: a different user must not be able
        to pass the write guard for someone else's custom resource."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(ResourceAccessDeniedError):
            service.guard_write_access(doc.rid, identity=bob, is_admin=False)

    def test_admin_bypasses_ownership_check(self, service, alice, admin_identity):
        doc = _make_custom_resource(service, alice)
        resolved = service.guard_write_access(doc.rid, identity=admin_identity, is_admin=True)
        assert resolved.rid == doc.rid

    def test_builtin_resource_blocked_for_non_admin_even_if_owner(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity)
        with pytest.raises(BuiltInWriteProtectedError):
            service.guard_write_access(doc.rid, identity=admin_identity, is_admin=False)

    def test_team_identity_ownership_matches_by_type_and_id(self, service):
        from mas.core.identity import Identity

        team = Identity.team("team-a")
        doc = _make_custom_resource(service, team)
        # Same team id, different display_name still matches.
        other_ref = Identity.team("team-a", display_name="Renamed Team")
        resolved = service.guard_write_access(doc.rid, identity=other_ref, is_admin=False)
        assert resolved.rid == doc.rid

        different_team = Identity.team("team-b")
        with pytest.raises(ResourceAccessDeniedError):
            service.guard_write_access(doc.rid, identity=different_team, is_admin=False)


# ────────────────────────────── visibility guards ──────────────────────────────

class TestVisibilityGuards:
    def test_get_visible_blocks_draft_builtin_for_non_admin(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.get_visible(doc.rid, is_admin=False)

    def test_get_visible_allows_draft_builtin_for_admin(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=False)
        resolved = service.get_visible(doc.rid, is_admin=True)
        assert resolved.rid == doc.rid

    def test_get_visible_allows_public_builtin_for_anyone(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=True)
        resolved = service.get_visible(doc.rid, is_admin=False)
        assert resolved.rid == doc.rid

    def test_validate_resource_blocks_probing_draft_builtins(self, service, admin_identity, alice):
        """Regression test: validate_resource must not let a non-admin probe
        a draft built-in's existence/schema via the validation endpoint."""
        doc = _make_builtin_resource(service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.validate_resource(doc.rid, identity=alice, is_admin=False)

    def test_get_cards_blocks_draft_builtin_for_non_admin(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=False)
        with pytest.raises(KeyError):
            service.get_cards([doc.rid], is_admin=False)

    def test_validate_resource_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: validate_resource must forward ``identity`` into
        ``get_visible`` so a non-owner cannot validate someone else's custom
        resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(KeyError):
            service.validate_resource(doc.rid, identity=bob, is_admin=False)

    def test_get_cards_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: get_cards must forward ``identity`` into
        ``get_visible`` so a non-owner cannot build a card for someone
        else's custom resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice)
        with pytest.raises(KeyError):
            service.get_cards([doc.rid], identity=bob, is_admin=False)

    def test_resolve_blocks_non_owner_on_custom_resource(self, service, alice, bob):
        """Regression test: resolve() must forward ``identity`` into
        ``get_visible`` so a non-owner cannot resolve/decrypt someone
        else's custom resource just by knowing its rid."""
        doc = _make_custom_resource(service, alice, bearer_token="alices-secret")
        with pytest.raises(KeyError):
            service.resolve(doc.rid, identity=bob, is_admin=False)


# ────────────────────────────── encryption ──────────────────────────────

class TestEncryption:
    def test_create_builtin_encrypts_schema_hint_only_secret_field(self, service, admin_identity):
        """bearer_token has no ENCRYPTED_FIELDS entry on the fake config class
        (mirroring the real McpProviderConfig) — it is only marked via
        SecretHint. The base cfg_dict must still be encrypted at rest."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="super-secret")

        raw = service.get(doc.rid)
        stored = raw.cfg_dict["bearer_token"]
        assert stored != "super-secret"
        # Behavior, not representation: it must be decryptable back to the
        # original secret via the same cipher used elsewhere (also exercised
        # end-to-end by test_resolve_decrypts_cfg_dict below).
        assert service._fields._cipher.decrypt(stored) == "super-secret"

    def test_resolve_decrypts_cfg_dict(self, service, admin_identity):
        """Regression test: resolve() must return plaintext secrets to
        downstream elements, not ciphertext."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="super-secret")

        resolved_config = service.resolve(doc.rid)
        assert resolved_config.bearer_token == "super-secret"


# ────────────────────────────── builtin overlay ──────────────────────────────

class TestBuiltinOverlay:
    def test_configure_builtin_raises_when_repo_unavailable(self, service_without_config_repo, admin_identity, alice):
        doc = _make_builtin_resource(service_without_config_repo, admin_identity)
        with pytest.raises(BuiltinConfigUnavailableError):
            service_without_config_repo.configure_builtin(
                doc.rid, identity=alice, config={"bearer_token": "mine"},
            )

    def test_configure_builtin_rejects_invalid_field_type(self, service, admin_identity, alice):
        """An overlay value that fails Pydantic validation against the
        element's config model must be rejected at configure-time, not
        silently persisted and only discovered later at resolve()."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        with pytest.raises(ValueError):
            service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": 12345})

        # Nothing should have been persisted from the rejected attempt.
        assert service.get_user_config(doc.rid, identity=alice) is None

    def test_configure_builtin_round_trips_through_get_user_config(self, service, admin_identity, alice):
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")

        service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        user_config = service.get_user_config(doc.rid, identity=alice)
        assert user_config["bearer_token"] == "alices-secret"

    def test_configure_builtin_overlay_takes_priority_in_resolve(self, service, admin_identity, alice, bob):
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        resolved_for_alice = service.resolve(doc.rid, identity=alice)
        resolved_for_bob = service.resolve(doc.rid, identity=bob)
        resolved_no_identity = service.resolve(doc.rid, identity=None)

        assert resolved_for_alice.bearer_token == "alices-secret"
        # Bob never configured his own overlay — he must NOT silently inherit
        # the admin's base-config secret (see `strip_unconfigured_secrets`).
        assert resolved_for_bob.bearer_token is None
        # identity=None (schema-only tooling) intentionally skips overlay
        # resolution entirely and keeps returning raw built-in defaults —
        # this is the documented, backward-compatible no-caller-identity path.
        assert resolved_no_identity.bearer_token == "default-secret"

    def test_resolve_strips_unconfigured_secret_even_without_any_overlays(
        self, service, admin_identity, alice,
    ):
        """Regression test: a per-user secret field baked into a built-in's
        shared base config (e.g. an admin's own bearer token, saved while
        testing connectivity before promoting it) must never leak to a user
        who has no overlay of their own — even when *nobody* has configured
        one yet."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="admins-own-secret")

        resolved = service.resolve(doc.rid, identity=alice)

        assert resolved.bearer_token is None

    def test_configure_builtin_encrypts_encrypted_fields_only_secret(self, service, admin_identity, alice):
        """``api_key`` is sensitive only via ``ENCRYPTED_FIELDS`` (no
        ``SecretHint``, like some real element configs). Regression test:
        the per-identity overlay must encrypt it at rest just like the base
        ``cfg_dict`` does via ``encrypt_fields``, not silently store it in
        plaintext because schema-hint scanning alone doesn't see it."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")

        service.configure_builtin(doc.rid, identity=alice, config={"api_key": "alices-api-key"})

        stored = service._builtin_user_config_repo.get(doc.rid, identity_to_key(alice))
        assert stored.fields["api_key"] != "alices-api-key"
        assert stored.fields["api_key"].startswith("gAAAAAB")

        user_config = service.get_user_config(doc.rid, identity=alice)
        assert user_config["api_key"] == "alices-api-key"

    def test_get_cards_passes_identity_through_for_overlay(self, service, admin_identity, alice):
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})

        captured = {}

        def fake_build_all_cards(configs):
            captured["configs"] = configs
            return {c.rid: c for c in configs}

        service._card_service.build_all_cards.side_effect = fake_build_all_cards

        service.get_cards([doc.rid], identity=alice, is_admin=False)

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
        self, service, admin_identity, bob,
    ):
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        captured = self._capture_ordered_configs(service, is_valid=False)

        service.validate_resource(doc.rid, identity=bob)

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is not None
        assert "bearer_token" in built.validation_override_error

    def test_validate_resource_does_not_flag_when_caller_has_overlay(
        self, service, admin_identity, alice,
    ):
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        service.configure_builtin(doc.rid, identity=alice, config={"bearer_token": "alices-secret"})
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, identity=alice)

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None

    def test_validate_resource_not_flagged_without_identity(
        self, service, admin_identity,
    ):
        """``identity=None`` (schema-only tooling) skips the overlay concept
        entirely, same as ``resolve()`` — it must not be flagged either."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="default-secret")
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, identity=None)

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None

    def test_custom_resource_is_never_flagged(self, service, alice):
        """The gate only applies to built-ins — a custom resource's own
        (possibly empty) secret field is the caller's own business, not a
        missing-overlay situation."""
        doc = _make_custom_resource(service, alice, bearer_token=None)
        captured = self._capture_ordered_configs(service, is_valid=True)

        service.validate_resource(doc.rid, identity=alice)

        built = next(c for c in captured["configs"] if c.rid == doc.rid)
        assert built.validation_override_error is None


# ────────────────────────────── card-visibility hint ──────────────────────────────

class TestCardVisibilityHint:
    """``CardHint`` (``hints.card``) must survive schema serialization
    end-to-end through ``get_builtin_schema()`` — the same JSON schema
    consumers use to know which fields to render on inventory cards for
    built-in vs. custom elements."""

    def test_card_hint_present_on_builtin_schema(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity)
        schema = service.get_builtin_schema(doc.rid, is_admin=True)

        endpoint_hints = schema["properties"]["endpoint"]["hints"]
        assert endpoint_hints["card"] == {"contexts": ["custom"]}

    def test_card_hint_untouched_by_read_only_annotation(self, service, admin_identity):
        """``get_builtin_schema`` adds ``read_only`` hints to non-configurable
        fields but must not strip or overwrite any pre-existing ``card`` hint
        while doing so."""
        doc = _make_builtin_resource(service, admin_identity)
        schema = service.get_builtin_schema(doc.rid, is_admin=True)

        endpoint_hints = schema["properties"]["endpoint"]["hints"]
        # `endpoint` has no ReadOnlyHint(read_only=False), so it becomes
        # locked for built-ins — but its `card` hint must still be intact.
        assert endpoint_hints["read_only"] == {"read_only": True}
        assert endpoint_hints["card"] == {"contexts": ["custom"]}


# ────────────────────────────── promote/demote lifecycle ──────────────────────────────

class TestPromoteDemote:
    def test_promote_custom_to_public_builtin(self, service, alice):
        doc = _make_custom_resource(service, alice)
        promoted, _ = service.promote_with_cascade(doc.rid)
        assert promoted.ownership == ResourceOwnership.BUILTIN
        assert promoted.visibility == ResourceVisibility.PUBLIC

    def test_demote_sets_draft_visibility(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=True)
        demoted = service.demote(doc.rid)
        assert demoted.visibility == ResourceVisibility.DRAFT

    def test_toggle_visibility_delegates_to_promote_and_demote(self, service, alice, admin_identity):
        custom = _make_custom_resource(service, alice)
        toggled_on, _ = service.toggle_visibility_with_cascade(custom.rid, available_to_all=True)
        assert toggled_on.visibility == ResourceVisibility.PUBLIC
        assert toggled_on.ownership == ResourceOwnership.BUILTIN

        toggled_off, _ = service.toggle_visibility_with_cascade(toggled_on.rid, available_to_all=False)
        assert toggled_off.visibility == ResourceVisibility.DRAFT


# ────────────────────────────── nested-dependency cascade ──────────────────────────────

class TestNestedDependencyCascade:
    """An agent/node can aggregate leaf elements (LLMs, providers, tools)
    via ``nested_refs``. Promoting the agent to "available to all" must
    cascade to those leaves, and demoting a leaf that a public agent still
    uses must be blocked."""

    def test_promote_cascades_to_not_yet_public_nested_refs(self, service, alice, admin_identity):
        llm = _make_custom_resource(service, alice, name="my-llm")
        agent = _make_custom_resource(service, alice, name="my-agent")
        _link_nested(service, agent, llm.rid)

        service.promote_with_cascade(agent.rid)

        promoted_llm = service.get(llm.rid)
        assert promoted_llm.ownership == ResourceOwnership.BUILTIN
        assert promoted_llm.visibility == ResourceVisibility.PUBLIC

    def test_promote_cascades_transitively_through_a_chain(self, service, alice):
        provider = _make_custom_resource(service, alice, name="my-provider")
        tool = _make_custom_resource(service, alice, name="my-tool")
        agent = _make_custom_resource(service, alice, name="my-agent-2")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)

        service.promote_with_cascade(agent.rid)

        assert service.get(tool.rid).visibility == ResourceVisibility.PUBLIC
        assert service.get(provider.rid).visibility == ResourceVisibility.PUBLIC

    def test_promote_does_not_touch_already_public_nested_refs(self, service, alice, admin_identity):
        llm = _make_builtin_resource(service, admin_identity, name="shared-llm", available_to_all=True)
        agent = _make_custom_resource(service, alice, name="agent-using-shared-llm")
        _link_nested(service, agent, llm.rid)

        service.promote_with_cascade(agent.rid)

        # No-op: still public, version unchanged by the cascade.
        assert service.get(llm.rid).version == llm.version

    def test_preview_cascade_targets_lists_not_yet_public_deps(self, service, alice):
        llm = _make_custom_resource(service, alice, name="preview-llm")
        agent = _make_custom_resource(service, alice, name="preview-agent")
        _link_nested(service, agent, llm.rid)

        targets = service.preview_cascade_targets(agent.rid)

        assert [t.rid for t in targets] == [llm.rid]

    def test_demote_blocked_when_public_agent_still_uses_it(self, service, alice):
        llm = _make_custom_resource(service, alice, name="blocked-llm")
        agent = _make_custom_resource(service, alice, name="blocking-agent")
        _link_nested(service, agent, llm.rid)
        service.promote_with_cascade(agent.rid)  # cascades llm to public too

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            service.demote(llm.rid)

        assert "blocking-agent" in str(exc_info.value)
        assert [d.rid for d in exc_info.value.dependents] == [agent.rid]

    def test_demote_allowed_once_dependent_agent_is_demoted(self, service, alice):
        llm = _make_custom_resource(service, alice, name="unblocked-llm")
        agent = _make_custom_resource(service, alice, name="unblocking-agent")
        _link_nested(service, agent, llm.rid)
        service.promote_with_cascade(agent.rid)

        service.demote(agent.rid)
        demoted_llm = service.demote(llm.rid)

        assert demoted_llm.visibility == ResourceVisibility.DRAFT

    def test_demote_blocked_transitively_through_a_chain(self, service, alice):
        provider = _make_custom_resource(service, alice, name="chain-provider")
        tool = _make_custom_resource(service, alice, name="chain-tool")
        agent = _make_custom_resource(service, alice, name="chain-agent")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)
        service.promote_with_cascade(agent.rid)  # cascades tool + provider to public

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            service.demote(provider.rid)

        assert {d.rid for d in exc_info.value.dependents} == {tool.rid, agent.rid}

    def test_demote_not_blocked_by_unrelated_draft_agent(self, service, alice):
        llm = _make_custom_resource(service, alice, name="free-llm")
        draft_agent = _make_custom_resource(service, alice, name="draft-agent")
        _link_nested(service, draft_agent, llm.rid)
        service.promote_with_cascade(llm.rid)  # llm becomes public on its own; agent stays custom/draft

        demoted = service.demote(llm.rid)
        assert demoted.visibility == ResourceVisibility.DRAFT

    def test_promote_rejects_cascade_through_disabled_category_dependency(self, service, alice):
        """Regression test: a dependency in a `builtin_disabled_categories()`
        category (e.g. a retriever) must reject the whole promotion instead
        of being silently skipped — leaving the parent public while it still
        references a resource that end users can never see would defeat the
        entire cascade-promotion guarantee."""
        retriever = _make_disabled_category_resource(service, alice)
        agent = _make_custom_resource(service, alice, name="agent-with-retriever-dep")
        _link_nested(service, agent, retriever.rid)

        with pytest.raises(ValueError, match="is not supported as a built-in resource"):
            service.promote_with_cascade(agent.rid)

        reloaded_agent = service.get(agent.rid)
        assert reloaded_agent.ownership == ResourceOwnership.CUSTOM
        assert reloaded_agent.visibility == ResourceVisibility.DRAFT

        reloaded_retriever = service.get(retriever.rid)
        assert reloaded_retriever.ownership == ResourceOwnership.CUSTOM
        assert reloaded_retriever.visibility == ResourceVisibility.DRAFT

    def test_update_builtin_rejects_cascade_through_disabled_category_dependency(
        self, service, alice, admin_identity,
    ):
        """Same guarantee via `update_builtin_with_cascade` (toggling an
        existing draft built-in to "available to all"): no public resource
        should ever be published if a dependency can't cascade."""
        retriever = _make_disabled_category_resource(service, alice)
        builtin_doc = _make_builtin_resource(
            service, admin_identity, name="draft-builtin-with-retriever-dep",
            available_to_all=False,
        )
        _link_nested(service, builtin_doc, retriever.rid)

        with pytest.raises(ValueError, match="is not supported as a built-in resource"):
            service.update_builtin_with_cascade(builtin_doc.rid, available_to_all=True)

        reloaded_builtin = service.get(builtin_doc.rid)
        assert reloaded_builtin.visibility == ResourceVisibility.DRAFT

        reloaded_retriever = service.get(retriever.rid)
        assert reloaded_retriever.ownership == ResourceOwnership.CUSTOM
        assert reloaded_retriever.visibility == ResourceVisibility.DRAFT

    def test_promote_parent_stays_draft_when_cascade_fails_midway(self, service, alice):
        """Regression: if `_cascade_promote_dependencies` raises mid-loop
        (e.g. a Mongo write error on the second dependency), the parent must
        NOT end up PUBLIC while a dependency remains DRAFT — that would break
        the cascade invariant."""
        llm = _make_custom_resource(service, alice, name="cascade-fail-llm")
        tool = _make_custom_resource(service, alice, name="cascade-fail-tool")
        agent = _make_custom_resource(service, alice, name="cascade-fail-agent")
        _link_nested(service, agent, llm.rid, tool.rid)

        original_update = service._store.update
        call_count = {"n": 0}

        def failing_update(doc):
            call_count["n"] += 1
            # Let the parent's intermediate DRAFT save through, then fail on
            # the first dependency write inside the cascade loop.
            if doc.rid in (llm.rid, tool.rid) and doc.visibility == ResourceVisibility.PUBLIC:
                raise RuntimeError("simulated Mongo write error")
            return original_update(doc)

        service._store.update = failing_update

        with pytest.raises(RuntimeError, match="simulated Mongo write error"):
            service.promote_with_cascade(agent.rid)

        reloaded_agent = service.get(agent.rid)
        assert reloaded_agent.visibility == ResourceVisibility.DRAFT
        assert reloaded_agent.ownership == ResourceOwnership.BUILTIN

        reloaded_llm = service.get(llm.rid)
        assert reloaded_llm.visibility == ResourceVisibility.DRAFT

        reloaded_tool = service.get(tool.rid)
        assert reloaded_tool.visibility == ResourceVisibility.DRAFT
