"""Uploads are stored per user: the same file name from two users never collides."""
import base64
import os
from unittest.mock import Mock

import pytest

from core.data_sources.types.document.registration import DocumentRegistration
from infrastructure.storage.local_file_storage import LocalFileStorage, user_upload_dir


def _file(content: bytes) -> list[dict]:
    return [{"name": "report.pdf", "content": base64.b64encode(content).decode()}]


def test_same_name_from_two_users_does_not_collide(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    a = storage.save_files(_file(b"alice"), owner="alice")[0]
    b = storage.save_files(_file(b"bob"), owner="bob")[0]
    assert a != b
    assert open(a, "rb").read() == b"alice"
    assert open(b, "rb").read() == b"bob"


def test_user_dirs_stay_inside_the_upload_folder(tmp_path):
    for owner in ("alice", "../../etc", "a/b", "bob@example.com"):
        d = user_upload_dir(str(tmp_path), owner)
        assert d.startswith(str(tmp_path) + "/") and ".." not in d.replace(str(tmp_path), "")


def test_registration_reads_the_file_where_the_uploader_stored_it(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    stored = storage.save_files(_file(b"alice"), owner="alice")[0]
    reg = DocumentRegistration(
        data_source_repository=Mock(), upload_by="alice", instance={"source_name": "report.pdf"},
        upload_folder=str(tmp_path), doc_validators=Mock(),
    )
    assert reg.source_data.doc_path == stored


def test_another_user_cannot_register_a_pending_upload_of_someone_else(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    stored = storage.save_files(_file(b"alice"), owner="alice")[0]
    reg = DocumentRegistration(
        data_source_repository=Mock(), upload_by="mallory", instance={"source_name": "report.pdf"},
        upload_folder=str(tmp_path), doc_validators=Mock(),
    )
    # Mallory's folder holds no such file: the registration fails instead of adopting Alice's upload.
    with pytest.raises(FileNotFoundError):
        reg.source_data
    assert os.path.exists(stored)
