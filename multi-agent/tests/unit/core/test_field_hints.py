"""Unit tests for ``mas.core.field_hints``, focused on ``CardHint`` — the
opt-in hint marking a field as displayable on an element's inventory card,
scoped by ownership context (``builtin`` / ``custom``).
"""
import pytest
from pydantic import ValidationError

from mas.core.field_hints import CardHint, SecretHint, ConditionalHint, combine_hints


class TestCardHint:
    def test_to_hints_shape(self):
        hint = CardHint(contexts=["custom"])
        assert hint.to_hints() == {"hints": {"card": {"contexts": ["custom"]}}}

    def test_supports_both_contexts(self):
        hint = CardHint(contexts=["builtin", "custom"])
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
        hint = CardHint(contexts=["custom"])
        assert hint.to_hints() == {"hints": {"card": {"contexts": ["custom"]}}}

    def test_empty_text_included_when_set(self):
        hint = CardHint(contexts=["builtin", "custom"], empty_text="All tools")
        assert hint.to_hints() == {
            "hints": {"card": {"contexts": ["builtin", "custom"], "empty_text": "All tools"}}
        }


class TestCombineHintsWithCardHint:
    def test_combines_with_other_hints(self):
        combined = combine_hints(
            ConditionalHint(visible_when={"auth_method": "access_token"}),
            CardHint(contexts=["custom"]),
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
            CardHint(contexts=["builtin", "custom"]),
        )
        assert "secret" in combined["hints"]
        assert "card" in combined["hints"]
