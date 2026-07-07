"""Unit tests for PromptShortcuts RootModel and BlueprintDraft integration."""
import pytest

from mas.blueprints.exceptions import PromptShortcutsValidationError
from mas.blueprints.models.blueprint import BlueprintDraft
from mas.blueprints.models.prompt_shortcuts import PromptShortcuts, MAX_PROMPT_SHORTCUTS


def _item(text: str, id: str | None = None) -> dict:
    entry: dict = {"text": text}
    if id is not None:
        entry["id"] = id
    return entry


class TestPromptShortcutsParse:
    def test_parse_accepts_valid_list_assigns_ids_and_strips_text(self):
        shortcuts = PromptShortcuts.parse([_item("  hello world  ")])
        assert len(shortcuts.root) == 1
        assert shortcuts.root[0].text == "hello world"
        assert len(shortcuts.root[0].id) == 8

    def test_parse_preserves_valid_id(self):
        shortcuts = PromptShortcuts.parse([_item("hi", id="a1b2c3d4")])
        assert shortcuts.root[0].id == "a1b2c3d4"

    def test_parse_empty_or_none_returns_empty(self):
        assert PromptShortcuts.parse(None).is_empty
        assert PromptShortcuts.parse([]).is_empty

    def test_parse_rejects_four_items(self):
        items = [_item(f"p{i}", id=f"{i:08x}") for i in range(4)]
        with pytest.raises(PromptShortcutsValidationError):
            PromptShortcuts.parse(items)

    def test_parse_rejects_duplicate_ids(self):
        with pytest.raises(PromptShortcutsValidationError):
            PromptShortcuts.parse([
                _item("one", id="a1b2c3d4"),
                _item("two", id="a1b2c3d4"),
            ])

    def test_parse_rejects_empty_text(self):
        with pytest.raises(PromptShortcutsValidationError):
            PromptShortcuts.parse([_item("   ")])

    def test_parse_ignores_legacy_kind_key(self):
        shortcuts = PromptShortcuts.parse([
            {"text": "hello", "kind": "manual"},
        ])
        assert shortcuts.root[0].text == "hello"
        assert not hasattr(shortcuts.root[0], "kind")


class TestPromptShortcutsFromSpec:
    def test_from_spec_missing_key_returns_empty(self):
        assert PromptShortcuts.from_spec({}).is_empty

    def test_from_spec_drops_bad_entries(self):
        shortcuts = PromptShortcuts.from_spec({
            "prompt_shortcuts": [
                {"text": "ok"},
                "not a dict",
                {"no_text": True},
                {"text": "  "},
            ],
        })
        assert len(shortcuts.root) == 1
        assert shortcuts.root[0].text == "ok"

    def test_from_spec_caps_at_max_and_drops_duplicates(self):
        shortcuts = PromptShortcuts.from_spec({
            "prompt_shortcuts": [
                _item("a", id="11111111"),
                _item("b", id="22222222"),
                _item("c", id="33333333"),
                _item("d", id="44444444"),
                _item("dup", id="11111111"),
            ],
        })
        assert shortcuts.count == MAX_PROMPT_SHORTCUTS
        ids = {p.id for p in shortcuts.root}
        assert ids == {"11111111", "22222222", "33333333"}

    def test_from_spec_never_raises(self):
        PromptShortcuts.from_spec({"prompt_shortcuts": "invalid"})


class TestPromptShortcutsSerialization:
    def test_to_storage_returns_none_when_empty(self):
        assert PromptShortcuts(()).to_storage() is None

    def test_to_storage_returns_list_of_dicts(self):
        storage = PromptShortcuts.parse([_item("x", id="abcd1234")]).to_storage()
        assert storage == [{"id": "abcd1234", "text": "x"}]

    def test_model_dump_json_is_array_not_wrapper(self):
        dumped = PromptShortcuts.parse([_item("x", id="abcd1234")]).model_dump(mode="json")
        assert isinstance(dumped, list)
        assert dumped == [{"id": "abcd1234", "text": "x"}]


class TestBlueprintDraftPromptShortcuts:
    def test_model_validate_coerces_list_to_prompt_shortcuts(self):
        draft = BlueprintDraft(**{
            "plan": [],
            "prompt_shortcuts": [_item("shortcut", id="abcd1234")],
        })
        assert isinstance(draft.prompt_shortcuts, PromptShortcuts)
        assert draft.prompt_shortcuts.root[0].text == "shortcut"

    def test_model_validate_dump_emits_array(self):
        draft = BlueprintDraft(**{
            "plan": [],
            "prompt_shortcuts": [_item("shortcut", id="abcd1234")],
        })
        dumped = draft.model_dump(mode="json")
        assert dumped["prompt_shortcuts"] == [{"id": "abcd1234", "text": "shortcut"}]

    def test_invalid_shortcuts_raise_domain_error(self):
        with pytest.raises(PromptShortcutsValidationError):
            BlueprintDraft(**{
                "plan": [],
                "prompt_shortcuts": [_item(f"p{i}", id=f"{i:08x}") for i in range(4)],
            })

    def test_mixed_errors_still_raise_shortcuts_domain_error(self):
        """Shortcut domain error propagates even when other fields are also invalid."""
        with pytest.raises(PromptShortcutsValidationError):
            BlueprintDraft(**{
                "prompt_shortcuts": [_item(f"p{i}", id=f"{i:08x}") for i in range(4)],
            })


class TestUpdateDraftShortcutMerge:
    def test_preserves_prompt_shortcuts_when_omitted(self):
        existing = {
            "plan": [],
            "prompt_shortcuts": [_item("keep me", id="abcd1234")],
        }
        incoming = {"plan": [], "name": "updated"}
        if "prompt_shortcuts" not in incoming:
            preserved = PromptShortcuts.from_spec(existing).to_storage()
            if preserved is not None:
                incoming = {**incoming, "prompt_shortcuts": preserved}
        assert incoming["prompt_shortcuts"] == [{"id": "abcd1234", "text": "keep me"}]

    def test_does_not_copy_when_incoming_has_key(self):
        existing = {
            "plan": [],
            "prompt_shortcuts": [_item("old", id="abcd1234")],
        }
        incoming = {
            "plan": [],
            "prompt_shortcuts": [_item("new", id="deadbeef")],
        }
        if "prompt_shortcuts" not in incoming:
            preserved = PromptShortcuts.from_spec(existing).to_storage()
            if preserved is not None:
                incoming = {**incoming, "prompt_shortcuts": preserved}
        assert incoming["prompt_shortcuts"] == [_item("new", id="deadbeef")]
