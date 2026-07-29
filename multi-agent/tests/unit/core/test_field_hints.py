"""Unit tests for ActionHint constants and ConditionalHint operator serialization."""

from __future__ import annotations

from mas.core.field_hints import (
    ActionHint,
    ConditionalHint,
    HintType,
    combine_hints,
)


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
