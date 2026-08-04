"""Regression test: reverse migration must abort when overlays contain
encrypted fields but no --encryption-key was provided."""
from unittest.mock import MagicMock, patch

import pytest

from global_utils.utils.crypto import FERNET_PREFIX


def _make_mock_db(overlay_fields: dict):
    """Build a mock pymongo database with one builtin_user_configs doc."""
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
    return db


def test_reverse_migration_raises_on_encrypted_field_without_key():
    from run.scripts.migrate_builtin_system import _run_reverse_migration_body

    overlay_fields = {"api_key": f"{FERNET_PREFIX}someciphertext"}
    db = _make_mock_db(overlay_fields)

    client = MagicMock()
    client.__getitem__ = lambda self, key: db

    with pytest.raises(RuntimeError, match="no --encryption-key was provided"):
        _run_reverse_migration_body(client, "TestDB", dry_run=False, cipher=None)


def test_reverse_migration_passes_plaintext_fields_without_key():
    from run.scripts.migrate_builtin_system import _run_reverse_migration_body

    overlay_fields = {"model_name": "gpt-4"}
    db = _make_mock_db(overlay_fields)

    client = MagicMock()
    client.__getitem__ = lambda self, key: db

    _run_reverse_migration_body(client, "TestDB", dry_run=False, cipher=None)
