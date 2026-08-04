"""Regression test: reverse migration must abort when overlays contain
encrypted fields but no --encryption-key was provided."""
from typing import Mapping, Tuple
from unittest.mock import MagicMock, patch

import pytest

from global_utils.utils.crypto import FERNET_PREFIX


def _make_mock_db(overlay_fields: Mapping[str, object]) -> Tuple[MagicMock, MagicMock, MagicMock]:
    """Build a mock pymongo database with one builtin_user_configs doc.

    Returns (db, resources_col, user_configs_col) so callers can assert
    on individual collection mocks.
    """
    cfg_doc = {
        "_id": "cfg1",
        "resource_id": "res-abc",
        "identity_key": "user@example.com",
        "fields": overlay_fields,
    }

    user_configs_col = MagicMock()
    user_configs_col.find.return_value = [cfg_doc]
    user_configs_col.count_documents.return_value = 1

    resources_col = MagicMock()
    resources_col.find.return_value = []
    resources_col.count_documents.return_value = 0

    db = MagicMock()
    db.__getitem__ = lambda self, key: {
        "resources": resources_col,
        "builtin_user_configs": user_configs_col,
    }[key]
    return db, resources_col, user_configs_col


def test_reverse_migration_raises_on_encrypted_field_without_key() -> None:
    from run.scripts.migrate_builtin_system import _run_reverse_migration_body

    overlay_fields = {"api_key": f"{FERNET_PREFIX}someciphertext"}
    db, resources_col, user_configs_col = _make_mock_db(overlay_fields)

    client = MagicMock()
    client.__getitem__ = lambda self, key: db

    with pytest.raises(RuntimeError, match="no --encryption-key was provided"):
        _run_reverse_migration_body(client, "TestDB", dry_run=False, cipher=None)

    resources_col.update_one.assert_not_called()
    resources_col.update_many.assert_not_called()
    user_configs_col.drop.assert_not_called()


def test_reverse_migration_passes_plaintext_fields_without_key() -> None:
    from run.scripts.migrate_builtin_system import _run_reverse_migration_body

    overlay_fields = {"model_name": "gpt-4"}
    db, resources_col, user_configs_col = _make_mock_db(overlay_fields)

    client = MagicMock()
    client.__getitem__ = lambda self, key: db

    _run_reverse_migration_body(client, "TestDB", dry_run=False, cipher=None)

    resources_col.update_one.assert_called()
    call_args = resources_col.update_one.call_args
    update_doc = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("update", {})
    assert "user_configs" in str(update_doc) or "$set" in str(update_doc)


def test_reverse_migration_raises_on_nested_encrypted_field_without_key() -> None:
    """Nested encrypted values must also trigger the abort."""
    from run.scripts.migrate_builtin_system import _run_reverse_migration_body

    overlay_fields = {"headers": {"Authorization": f"{FERNET_PREFIX}nestedcipher"}}
    db, resources_col, user_configs_col = _make_mock_db(overlay_fields)

    client = MagicMock()
    client.__getitem__ = lambda self, key: db

    with pytest.raises(RuntimeError, match="no --encryption-key was provided"):
        _run_reverse_migration_body(client, "TestDB", dry_run=False, cipher=None)

    resources_col.update_one.assert_not_called()
