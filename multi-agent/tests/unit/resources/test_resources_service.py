"""Unit tests for ResourcesService covering the security/correctness fixes:

- IDOR guard on update/delete (guard_write_access)
- Draft-builtin visibility enforcement (get_visible / validate_resource / get_cards)
- Secret encryption consistency (schema-hint-only secrets + duplicate_builtin)
- resolve() decrypting cfg_dict while merging the builtin overlay
- configure_builtin() failing loudly when no repo is configured
"""
import pytest

from mas.core.enums import ResourceOwnership, ResourceVisibility
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    BuiltinConfigUnavailableError,
    BuiltinDependentsPublicError,
)
from mas.resources.models import Resource

from tests.unit.resources.conftest import FAKE_CATEGORY, FAKE_TYPE


# ────────────────────────────── helpers ──────────────────────────────

def _make_custom_resource(service, identity, name="custom-1", bearer_token=None):
    return service.create(
        identity=identity,
        category=FAKE_CATEGORY,
        type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://a.example"},
    )


def _make_builtin_resource(service, admin_identity, name="builtin-1", available_to_all=True, bearer_token="s3cr3t"):
    return service.create_builtin(
        identity=admin_identity,
        category=FAKE_CATEGORY,
        type=FAKE_TYPE,
        name=name,
        config={"bearer_token": bearer_token, "endpoint": "https://b.example"},
        available_to_all=available_to_all,
    )


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


# ────────────────────────────── encryption ──────────────────────────────

class TestEncryption:
    def test_create_builtin_encrypts_schema_hint_only_secret_field(self, service, admin_identity):
        """bearer_token has no ENCRYPTED_FIELDS entry on the fake config class
        (mirroring the real McpProviderConfig) — it is only marked via
        SecretHint. The base cfg_dict must still be encrypted at rest."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="super-secret")

        raw = service.get(doc.rid)
        assert raw.cfg_dict["bearer_token"] != "super-secret"
        assert raw.cfg_dict["bearer_token"].startswith("gAAAAAB")

    def test_resolve_decrypts_cfg_dict(self, service, admin_identity):
        """Regression test: resolve() must return plaintext secrets to
        downstream elements, not ciphertext."""
        doc = _make_builtin_resource(service, admin_identity, bearer_token="super-secret")

        resolved_config = service.resolve(doc.rid)
        assert resolved_config.bearer_token == "super-secret"

    def test_duplicate_builtin_does_not_double_encrypt(self, service, admin_identity, alice):
        """Regression test: duplicating a built-in must decrypt cfg_dict
        before re-encrypting, otherwise the secret is corrupted."""
        source = _make_builtin_resource(service, admin_identity, bearer_token="super-secret")

        clone = service.duplicate_builtin(source.rid, identity=alice, name="my-clone")

        assert clone.ownership == ResourceOwnership.CUSTOM
        resolved = service.resolve(clone.rid)
        assert resolved.bearer_token == "super-secret"

    def test_duplicate_builtin_with_override_encrypts_new_value(self, service, admin_identity, alice):
        source = _make_builtin_resource(service, admin_identity, bearer_token="original-secret")

        clone = service.duplicate_builtin(
            source.rid, identity=alice, name="my-clone-2",
            config_overrides={"bearer_token": "overridden-secret"},
        )

        raw = service.get(clone.rid)
        assert raw.cfg_dict["bearer_token"] != "overridden-secret"
        resolved = service.resolve(clone.rid)
        assert resolved.bearer_token == "overridden-secret"


# ────────────────────────────── builtin overlay ──────────────────────────────

class TestBuiltinOverlay:
    def test_configure_builtin_raises_when_repo_unavailable(self, service_without_config_repo, admin_identity, alice):
        doc = _make_builtin_resource(service_without_config_repo, admin_identity)
        with pytest.raises(BuiltinConfigUnavailableError):
            service_without_config_repo.configure_builtin(
                doc.rid, identity=alice, config={"bearer_token": "mine"},
            )

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
        assert resolved_for_bob.bearer_token == "default-secret"
        assert resolved_no_identity.bearer_token == "default-secret"

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


# ────────────────────────────── promote/demote lifecycle ──────────────────────────────

class TestPromoteDemote:
    def test_promote_custom_to_public_builtin(self, service, alice):
        doc = _make_custom_resource(service, alice)
        promoted = service.promote(doc.rid)
        assert promoted.ownership == ResourceOwnership.BUILTIN
        assert promoted.visibility == ResourceVisibility.PUBLIC

    def test_demote_sets_draft_visibility(self, service, admin_identity):
        doc = _make_builtin_resource(service, admin_identity, available_to_all=True)
        demoted = service.demote(doc.rid)
        assert demoted.visibility == ResourceVisibility.DRAFT

    def test_toggle_visibility_delegates_to_promote_and_demote(self, service, alice, admin_identity):
        custom = _make_custom_resource(service, alice)
        toggled_on = service.toggle_visibility(custom.rid, available_to_all=True)
        assert toggled_on.visibility == ResourceVisibility.PUBLIC
        assert toggled_on.ownership == ResourceOwnership.BUILTIN

        toggled_off = service.toggle_visibility(toggled_on.rid, available_to_all=False)
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

        service.promote(agent.rid)

        promoted_llm = service.get(llm.rid)
        assert promoted_llm.ownership == ResourceOwnership.BUILTIN
        assert promoted_llm.visibility == ResourceVisibility.PUBLIC

    def test_promote_cascades_transitively_through_a_chain(self, service, alice):
        provider = _make_custom_resource(service, alice, name="my-provider")
        tool = _make_custom_resource(service, alice, name="my-tool")
        agent = _make_custom_resource(service, alice, name="my-agent-2")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)

        service.promote(agent.rid)

        assert service.get(tool.rid).visibility == ResourceVisibility.PUBLIC
        assert service.get(provider.rid).visibility == ResourceVisibility.PUBLIC

    def test_promote_does_not_touch_already_public_nested_refs(self, service, alice, admin_identity):
        llm = _make_builtin_resource(service, admin_identity, name="shared-llm", available_to_all=True)
        agent = _make_custom_resource(service, alice, name="agent-using-shared-llm")
        _link_nested(service, agent, llm.rid)

        service.promote(agent.rid)

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
        service.promote(agent.rid)  # cascades llm to public too

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            service.demote(llm.rid)

        assert "blocking-agent" in str(exc_info.value)
        assert [d.rid for d in exc_info.value.dependents] == [agent.rid]

    def test_demote_allowed_once_dependent_agent_is_demoted(self, service, alice):
        llm = _make_custom_resource(service, alice, name="unblocked-llm")
        agent = _make_custom_resource(service, alice, name="unblocking-agent")
        _link_nested(service, agent, llm.rid)
        service.promote(agent.rid)

        service.demote(agent.rid)
        demoted_llm = service.demote(llm.rid)

        assert demoted_llm.visibility == ResourceVisibility.DRAFT

    def test_demote_blocked_transitively_through_a_chain(self, service, alice):
        provider = _make_custom_resource(service, alice, name="chain-provider")
        tool = _make_custom_resource(service, alice, name="chain-tool")
        agent = _make_custom_resource(service, alice, name="chain-agent")
        _link_nested(service, tool, provider.rid)
        _link_nested(service, agent, tool.rid)
        service.promote(agent.rid)  # cascades tool + provider to public

        with pytest.raises(BuiltinDependentsPublicError) as exc_info:
            service.demote(provider.rid)

        assert {d.rid for d in exc_info.value.dependents} == {tool.rid, agent.rid}

    def test_demote_not_blocked_by_unrelated_draft_agent(self, service, alice):
        llm = _make_custom_resource(service, alice, name="free-llm")
        draft_agent = _make_custom_resource(service, alice, name="draft-agent")
        _link_nested(service, draft_agent, llm.rid)
        service.promote(llm.rid)  # llm becomes public on its own; agent stays custom/draft

        demoted = service.demote(llm.rid)
        assert demoted.visibility == ResourceVisibility.DRAFT
