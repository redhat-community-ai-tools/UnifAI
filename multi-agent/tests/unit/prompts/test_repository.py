"""Unit tests for MongoScheduledPromptRepository.

Tests are isolated by patching pymongo.MongoClient with an in-memory
mock collection that supports the basic operations used by the repository.

Covers: CRUD, identity-scoped queries, blueprint queries, record_run.
(Test Plan sections 2.1–2.3b)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from mas.core.identity import Identity
from mas.prompts.models import (
    RunOutcome,
    ScheduleDefinition,
    ScheduleOverlapPolicy,
    ScheduleStatus,
    ScheduledPrompt,
)


def _make_prompt(identity, blueprint_id="bp-1", status=ScheduleStatus.ACTIVE, **kwargs):
    return ScheduledPrompt(
        blueprint_id=blueprint_id,
        identity=identity,
        text=kwargs.pop("text", "test"),
        schedule=kwargs.pop(
            "schedule", ScheduleDefinition(interval=timedelta(minutes=15))
        ),
        schedule_status=status,
        **kwargs,
    )


class InMemoryCollection:
    """Minimal in-memory MongoDB collection substitute for testing."""

    def __init__(self):
        self._docs = []
        self._indexes = []

    def create_index(self, *args, **kwargs):
        self._indexes.append(args)

    def insert_one(self, doc):
        for existing in self._docs:
            if existing.get("id") == doc.get("id"):
                raise Exception("DuplicateKeyError")
        self._docs.append(dict(doc))

    def find_one(self, query):
        for doc in self._docs:
            if self._matches(doc, query):
                return dict(doc)
        return None

    def find(self, query=None):
        query = query or {}
        results = [dict(d) for d in self._docs if self._matches(d, query)]
        return _Cursor(results)

    def update_one(self, query, update):
        for i, doc in enumerate(self._docs):
            if self._matches(doc, query):
                self._apply_update(doc, update)
                return MagicMock(modified_count=1, matched_count=1)
        return MagicMock(modified_count=0, matched_count=0)

    def delete_one(self, query):
        for i, doc in enumerate(self._docs):
            if self._matches(doc, query):
                self._docs.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def count_documents(self, query):
        return sum(1 for d in self._docs if self._matches(d, query))

    def drop_index(self, name):
        pass

    def _matches(self, doc, query):
        for key, val in query.items():
            doc_val = self._get_nested(doc, key)
            if isinstance(val, dict):
                if "$in" in val:
                    if doc_val not in val["$in"]:
                        return False
                elif "$ne" in val:
                    ne_val = val["$ne"]
                    if isinstance(doc_val, list):
                        if ne_val in doc_val:
                            return False
                    else:
                        if doc_val == ne_val:
                            return False
                elif "$type" in val:
                    pass  # skip type checks
                else:
                    if doc_val != val:
                        return False
            else:
                if isinstance(doc_val, list):
                    if val not in doc_val:
                        return False
                elif doc_val != val:
                    return False
        return True

    def _get_nested(self, doc, key):
        parts = key.split(".")
        return self._resolve_path(doc, parts)

    def _resolve_path(self, val, parts):
        if not parts:
            return val
        if isinstance(val, dict):
            return self._resolve_path(val.get(parts[0]), parts[1:])
        if isinstance(val, list):
            results = []
            for item in val:
                r = self._resolve_path(item, parts)
                if r is not None:
                    results.append(r)
            return results if results else None
        return None

    def _apply_update(self, doc, update):
        if "$set" in update:
            for key, val in update["$set"].items():
                self._set_nested(doc, key, val)
        if "$inc" in update:
            for key, val in update["$inc"].items():
                current = self._get_nested(doc, key) or 0
                self._set_nested(doc, key, current + val)
        if "$push" in update:
            for key, spec in update["$push"].items():
                current = self._get_nested(doc, key) or []
                if isinstance(spec, dict) and "$each" in spec:
                    current.extend(spec["$each"])
                    if "$slice" in spec:
                        s = spec["$slice"]
                        current = current[s:] if s < 0 else current[:s]
                else:
                    current.append(spec)
                self._set_nested(doc, key, current)

    def _set_nested(self, doc, key, value):
        parts = key.split(".")
        for p in parts[:-1]:
            if p not in doc or not isinstance(doc[p], dict):
                doc[p] = {}
            doc = doc[p]
        doc[parts[-1]] = value


class _Cursor:
    def __init__(self, results):
        self._results = results
        self._skip = 0
        self._limit = 0

    def sort(self, key, direction=-1):
        self._results.sort(key=lambda d: d.get(key, ""), reverse=(direction == -1))
        return self

    def skip(self, n):
        self._skip = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def __iter__(self):
        results = self._results[self._skip:]
        if self._limit:
            results = results[: self._limit]
        return iter(results)


@pytest.fixture
def in_memory_col():
    return InMemoryCollection()


@pytest.fixture
def repo(in_memory_col):
    """Create repository with in-memory collection."""
    with patch("outbound.mongo.scheduled_prompt_repository.pymongo.MongoClient") as mock_client, \
         patch("outbound.mongo.scheduled_prompt_repository.get_mongo_url", return_value="mongodb://localhost"):
        mock_db = MagicMock()
        mock_db.__getitem__ = lambda self, key: in_memory_col
        mock_client.return_value.__getitem__ = lambda self, key: mock_db

        from outbound.mongo.scheduled_prompt_repository import MongoScheduledPromptRepository

        r = MongoScheduledPromptRepository.__new__(MongoScheduledPromptRepository)
        r._col = in_memory_col
        return r


@pytest.fixture
def identity_a():
    return Identity.user("user-a")


@pytest.fixture
def identity_b():
    return Identity.user("user-b")


@pytest.fixture
def team_identity():
    return Identity.team("team-1")


# ═══════════════════════════════════════════════════════════════════
# 2.1 CRUD
# ═══════════════════════════════════════════════════════════════════

class TestRepoCRUD:
    def test_save_load_roundtrip(self, repo, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        loaded = repo.load(prompt.id)
        assert loaded.id == prompt.id
        assert loaded.text == prompt.text
        assert loaded.blueprint_id == prompt.blueprint_id

    def test_save_sets_timestamps(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        doc = in_memory_col.find_one({"id": prompt.id})
        assert "created_at" in doc
        assert "updated_at" in doc

    def test_update_changes_updated_at(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        doc1 = in_memory_col.find_one({"id": prompt.id})
        original_updated = doc1["updated_at"]

        import time
        time.sleep(0.01)
        updated_prompt = prompt.model_copy(update={"text": "new text"})
        repo.update(updated_prompt)
        doc2 = in_memory_col.find_one({"id": prompt.id})
        assert doc2["updated_at"] >= original_updated

    def test_load_nonexistent_raises_keyerror(self, repo):
        with pytest.raises(KeyError):
            repo.load("does-not-exist")

    def test_delete_existing(self, repo, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        result = repo.delete(prompt.id)
        assert result is True
        with pytest.raises(KeyError):
            repo.load(prompt.id)

    def test_delete_nonexistent(self, repo):
        result = repo.delete("no-such-id")
        assert result is False

    def test_update_nonexistent(self, repo, identity_a):
        prompt = _make_prompt(identity_a)
        result = repo.update(prompt)
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# 2.2 Identity-Scoped Queries
# ═══════════════════════════════════════════════════════════════════

class TestRepoIdentityScoped:
    def test_list_by_identity_personal(self, repo, identity_a, identity_b):
        for _ in range(3):
            repo.save(_make_prompt(identity_a))
        for _ in range(2):
            repo.save(_make_prompt(identity_b))
        result = repo.list_by_identity(identity_a)
        assert len(result) == 3

    def test_list_by_identity_team(self, repo, team_identity, identity_a):
        repo.save(_make_prompt(team_identity))
        repo.save(_make_prompt(identity_a))
        result = repo.list_by_identity(team_identity)
        assert len(result) == 1

    def test_list_includes_paused(self, repo, identity_a):
        repo.save(_make_prompt(identity_a, status=ScheduleStatus.PAUSED))
        result = repo.list_by_identity(identity_a)
        assert len(result) == 1

    def test_list_includes_completed(self, repo, identity_a):
        repo.save(_make_prompt(identity_a, status=ScheduleStatus.COMPLETED))
        result = repo.list_by_identity(identity_a)
        assert len(result) == 1

    def test_pagination(self, repo, identity_a):
        for _ in range(15):
            repo.save(_make_prompt(identity_a))
        result = repo.list_by_identity(identity_a, skip=5, limit=5)
        assert len(result) == 5

    def test_empty_result_for_new_identity(self, repo, identity_a):
        result = repo.list_by_identity(identity_a)
        assert result == []


# ═══════════════════════════════════════════════════════════════════
# 2.3 Blueprint Queries
# ═══════════════════════════════════════════════════════════════════

class TestRepoBlueprintQueries:
    def test_find_by_blueprint_basic(self, repo, identity_a):
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-B"))
        result = repo.find_by_blueprint("bp-A")
        assert len(result) == 2

    def test_count_active_by_blueprint_active(self, repo, identity_a):
        for _ in range(3):
            repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        count = repo.count_active_by_blueprint("bp-A")
        assert count == 3

    def test_count_active_paused_included(self, repo, identity_a):
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A", status=ScheduleStatus.PAUSED))
        count = repo.count_active_by_blueprint("bp-A")
        assert count == 3

    def test_count_active_completed_excluded(self, repo, identity_a):
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A"))
        repo.save(_make_prompt(identity_a, blueprint_id="bp-A", status=ScheduleStatus.COMPLETED))
        count = repo.count_active_by_blueprint("bp-A")
        assert count == 2


# ═══════════════════════════════════════════════════════════════════
# 2.3b record_run (Ring Buffer)
# ═══════════════════════════════════════════════════════════════════

class TestRepoRecordRun:
    def test_increments_total(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        now = datetime.now(timezone.utc)
        repo.record_run(prompt.id, "s1", RunOutcome.COMPLETED, now)
        doc = in_memory_col.find_one({"id": prompt.id})
        assert doc["run_stats"]["total_runs"] == 1

    def test_sets_last_run_at(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        now = datetime.now(timezone.utc)
        repo.record_run(prompt.id, "s1", RunOutcome.COMPLETED, now)
        doc = in_memory_col.find_one({"id": prompt.id})
        assert doc["run_stats"]["last_run_at"] == now

    def test_pushes_to_recent_statuses(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        now = datetime.now(timezone.utc)
        repo.record_run(prompt.id, "s1", RunOutcome.COMPLETED, now)
        doc = in_memory_col.find_one({"id": prompt.id})
        assert len(doc["run_stats"]["recent_statuses"]) == 1
        assert doc["run_stats"]["recent_statuses"][0]["session_id"] == "s1"

    def test_ring_buffer_caps_at_8(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        now = datetime.now(timezone.utc)
        for i in range(10):
            repo.record_run(prompt.id, f"s{i}", RunOutcome.COMPLETED, now)
        doc = in_memory_col.find_one({"id": prompt.id})
        assert len(doc["run_stats"]["recent_statuses"]) == 8

    def test_nonexistent_prompt_no_error(self, repo):
        now = datetime.now(timezone.utc)
        repo.record_run("nonexistent", "s1", RunOutcome.COMPLETED, now)

    def test_status_values_stored(self, repo, in_memory_col, identity_a):
        prompt = _make_prompt(identity_a)
        repo.save(prompt)
        now = datetime.now(timezone.utc)
        repo.record_run(prompt.id, "s1", RunOutcome.COMPLETED, now)
        repo.record_run(prompt.id, "s2", RunOutcome.FAILED, now)
        doc = in_memory_col.find_one({"id": prompt.id})
        statuses = [e["status"] for e in doc["run_stats"]["recent_statuses"]]
        assert "COMPLETED" in statuses
        assert "FAILED" in statuses
