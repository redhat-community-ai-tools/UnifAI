"""Unit tests for ``mas.core.field_hints``.

Covers ``CardHint`` — the opt-in hint marking a field as displayable on an
element's inventory card, scoped by ownership context (``builtin`` /
``custom``) — as well as ``ActionHint`` constants and ``ConditionalHint``
operator serialization.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from mas.core.field_hints import (
    ActionHint,
    CardContext,
    CardHint,
    ConditionalHint,
    HintType,
    SecretHint,
    combine_hints,
)


class TestCardHint:
    def test_to_hints_shape(self):
        hint = CardHint(contexts=[CardContext.CUSTOM])
        assert hint.to_hints() == {"hints": {"card": {"contexts": ["custom"]}}}

    def test_supports_both_contexts(self):
        hint = CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM])
        assert hint.to_hints()["hints"]["card"]["contexts"] == ["builtin", "custom"]

    def test_contexts_is_required(self):
        """Opt-in only: a field must explicitly declare which context(s) it
        appears in — there is no default-visible behavior."""
        with pytest.raises(ValidationError):
            CardHint()

    def test_rejects_unknown_context(self):
        with pytest.raises(ValidationError):
            CardHint(contexts=["admin"])

    def test_empty_text_omitted_by_default(self):
        """`empty_text` is optional and excluded from the serialized hint
        when unset, so existing fields without it keep their exact shape."""
        hint = CardHint(contexts=[CardContext.CUSTOM])
        assert hint.to_hints() == {"hints": {"card": {"contexts": ["custom"]}}}

    def test_empty_text_included_when_set(self):
        hint = CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM], empty_text="All tools")
        assert hint.to_hints() == {
            "hints": {"card": {"contexts": ["builtin", "custom"], "empty_text": "All tools"}}
        }


class TestCombineHintsWithCardHint:
    def test_combines_with_other_hints(self):
        combined = combine_hints(
            ConditionalHint(visible_when={"auth_method": "access_token"}),
            CardHint(contexts=[CardContext.CUSTOM]),
        )
        assert combined["hints"]["conditional"]["visible_when"] == {"auth_method": "access_token"}
        assert combined["hints"]["card"]["contexts"] == ["custom"]

    def test_secret_and_card_can_coexist_in_schema(self):
        """The hint system itself doesn't forbid combining `secret` with
        `card` — the hard "never render a secret on a card" rule is enforced
        by card-rendering consumers, not by the schema. This test just
        documents that both hints can be attached and read back together."""
        combined = combine_hints(
            SecretHint(allow_reveal=True),
            CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]),
        )
        assert "secret" in combined["hints"]
        assert "card" in combined["hints"]


class TestActionHintConstants:
    def test_to_hints_includes_constants(self):
        hint = ActionHint(
            action_uid="auth.list_servers",
            hint_type=HintType.POPULATE,
            field_mapping="servers",
            constants={"category": "a2a"},
        )
        payload = hint.to_hints()

        assert "action" in payload["hints"]
        assert payload["hints"]["action"]["constants"] == {"category": "a2a"}
        assert payload["hints"]["action"]["action_uid"] == "auth.list_servers"

    def test_combine_hints_preserves_constants(self):
        combined = combine_hints(
            ActionHint(
                action_uid="auth.list_servers",
                hint_type=HintType.POPULATE,
                constants={"category": "mcp"},
            ),
            ConditionalHint(
                visible_when={"auth_method": {"not_in": ["none", "access_token"]}},
            ),
        )

        assert combined["hints"]["action"]["constants"] == {"category": "mcp"}
        assert combined["hints"]["conditional"]["visible_when"] == {
            "auth_method": {"not_in": ["none", "access_token"]},
        }


class TestConditionalHintOperators:
    def test_model_dump_preserves_not_in_operator(self):
        hint = ConditionalHint(
            visible_when={"auth_method": {"not_in": ["none", "access_token"]}},
        )
        dumped = hint.model_dump()

        assert dumped["visible_when"]["auth_method"] == {
            "not_in": ["none", "access_token"],
        }

    def test_to_hints_preserves_in_operator(self):
        hint = ConditionalHint(
            visible_when={"auth_method": {"in": ["oauth", "sso"]}},
        )
        payload = hint.to_hints()

        assert payload["hints"]["conditional"]["visible_when"] == {
            "auth_method": {"in": ["oauth", "sso"]},
        }

    def test_to_hints_preserves_scalar_equality(self):
        hint = ConditionalHint(visible_when={"auth_method": "access_token"})
        payload = hint.to_hints()

        assert payload["hints"]["conditional"]["visible_when"] == {
            "auth_method": "access_token",
        }
