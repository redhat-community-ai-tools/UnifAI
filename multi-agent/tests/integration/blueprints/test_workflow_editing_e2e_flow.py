"""
E2E integration tests simulating the UI flow for editing and saving workflows multiple times.

These tests verify that:
  1. A workflow can be edited and saved 3-4 times in succession without any issues.
  2. The version history is correctly populated with snapshots for each edit.
  3. Any historical version can be retrieved and previewed.
  4. Restoring to a previous version is stable and creates a new version with the restored content.
  5. Concurrent modification (OCC) is enforced to prevent overwriting.
"""

from __future__ import annotations

import pytest
import mongomock

from flask import Flask
from adapters.inbound.flask.endpoints.blueprints import blueprints_bp
from adapters.outbound.mongo.blueprint_repository import MongoBlueprintRepository
from adapters.outbound.mongo.blueprint_version_repository import MongoBlueprintVersionRepository
from lib.mas.blueprints.service import BlueprintService


@pytest.fixture()
def mongo_client():
    return mongomock.MongoClient()


@pytest.fixture()
def bp_col(mongo_client):
    return mongo_client["test"]["blueprints"]


@pytest.fixture()
def ver_col(mongo_client):
    return mongo_client["test"]["blueprint_versions"]


@pytest.fixture()
def bp_repo(bp_col):
    return MongoBlueprintRepository(col=bp_col)


@pytest.fixture()
def ver_repo(ver_col):
    r = MongoBlueprintVersionRepository(col=ver_col)
    r.ensure_indexes()
    return r


@pytest.fixture()
def service(bp_repo, ver_repo):
    return BlueprintService(repo=bp_repo, version_repo=ver_repo)


@pytest.fixture()
def app(service):
    """Flask test app with the real service and mongomock wired in."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.blueprint_service = service
    flask_app.register_blueprint(blueprints_bp)
    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


class TestWorkflowEditingE2EFlow:
    def test_workflow_multiple_edits_and_saves_e2e(self, client):
        """
        Test editing and saving a workflow 4 times in succession.
        Verifies that:
          - The workflow is created with version 1.
          - Each subsequent edit increments the version and creates a snapshot.
          - The version history correctly lists all snapshots in descending order.
          - We can load details of any specific version.
          - Restoring to an older version (e.g., version 2) works and creates a new version (version 6).
        """
        # 1. Create a new workflow (blueprint) - Version 1
        identity_data = {"type": "user", "id": "u-bob"}
        spec_v1 = {
            "name": "E2E Workflow",
            "description": "Initial draft",
            "plan": []
        }
        
        save_resp = client.post(
            "/blueprint.save",
            json={
                "identity": identity_data,
                "spec_dict": spec_v1,
            }
        )
        assert save_resp.status_code == 201
        save_body = save_resp.get_json()
        assert save_body["success"] is True
        blueprint_id = save_body["data"]["blueprint_id"]
        assert blueprint_id is not None

        # Verify initial state (version 1)
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["version"] == 1
        assert get_resp.get_json()["data"]["spec_dict"] == spec_v1

        # 2. Edit and Save 1 (v1 -> v2)
        spec_v2 = {
            "name": "E2E Workflow",
            "description": "First Edit",
            "plan": [{"uid": "step-1", "type": "trigger"}]
        }
        update_resp1 = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_v2,
                "change_summary": "Added trigger step",
                "user_id": "u-bob",
            }
        )
        assert update_resp1.status_code == 200
        assert update_resp1.get_json()["success"] is True

        # Verify state is now version 2
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["version"] == 2
        assert get_resp.get_json()["data"]["spec_dict"] == spec_v2

        # 3. Edit and Save 2 (v2 -> v3)
        spec_v3 = {
            "name": "E2E Workflow",
            "description": "Second Edit",
            "plan": [
                {"uid": "step-1", "type": "trigger"},
                {"uid": "step-2", "type": "action"}
            ]
        }
        update_resp2 = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_v3,
                "change_summary": "Added action step",
                "user_id": "u-bob",
            }
        )
        assert update_resp2.status_code == 200
        assert update_resp2.get_json()["success"] is True

        # Verify state is now version 3
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["version"] == 3
        assert get_resp.get_json()["data"]["spec_dict"] == spec_v3

        # 4. Edit and Save 3 (v3 -> v4)
        spec_v4 = {
            "name": "E2E Workflow",
            "description": "Third Edit",
            "plan": [
                {"uid": "step-1", "type": "trigger"},
                {"uid": "step-2", "type": "action"},
                {"uid": "step-3", "type": "notification"}
            ]
        }
        update_resp3 = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_v4,
                "change_summary": "Added notification step",
                "user_id": "u-bob",
            }
        )
        assert update_resp3.status_code == 200
        assert update_resp3.get_json()["success"] is True

        # Verify state is now version 4
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["version"] == 4
        assert get_resp.get_json()["data"]["spec_dict"] == spec_v4

        # 5. Edit and Save 4 (v4 -> v5)
        spec_v5 = {
            "name": "E2E Workflow - Final",
            "description": "Fourth Edit",
            "plan": [
                {"uid": "step-1", "type": "trigger"},
                {"uid": "step-2", "type": "action"},
                {"uid": "step-3", "type": "notification"}
            ]
        }
        update_resp4 = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_v5,
                "change_summary": "Renamed workflow",
                "user_id": "u-bob",
            }
        )
        assert update_resp4.status_code == 200
        assert update_resp4.get_json()["success"] is True

        # Verify state is now version 5
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        assert get_resp.get_json()["data"]["version"] == 5
        assert get_resp.get_json()["data"]["spec_dict"] == spec_v5

        # 6. Verify Version History
        history_resp = client.get(f"/blueprint.versions.list?blueprint_id={blueprint_id}")
        assert history_resp.status_code == 200
        history_body = history_resp.get_json()
        assert history_body["success"] is True
        history_data = history_body["data"]
        
        # There should be 4 snapshots (for versions 4, 3, 2, 1)
        assert history_data["total"] == 4
        versions = [item["version"] for item in history_data["items"]]
        assert versions == [4, 3, 2, 1]
        
        # Verify summaries match
        assert history_data["items"][0]["change_summary"] == "Renamed workflow" # v4 snapshot has summary of the edit that moved it to v5
        assert history_data["items"][1]["change_summary"] == "Added notification step"
        assert history_data["items"][2]["change_summary"] == "Added action step"
        assert history_data["items"][3]["change_summary"] == "Added trigger step"

        # 7. Verify we can load any specific version detail (Preview)
        # Let's preview version 2
        v2_resp = client.get(f"/blueprint.version.get?blueprint_id={blueprint_id}&version=2")
        assert v2_resp.status_code == 200
        v2_body = v2_resp.get_json()
        assert v2_body["success"] is True
        assert v2_body["data"]["version"] == 2
        assert v2_body["data"]["spec_dict_snapshot"] == spec_v2

        # 8. Verify Restore to version 2
        restore_resp = client.post(
            "/blueprint.version.restore",
            json={
                "blueprint_id": blueprint_id,
                "version": 2,
                "user_id": "u-bob"
            }
        )
        assert restore_resp.status_code == 200
        restore_body = restore_resp.get_json()
        assert restore_body["success"] is True
        assert restore_body["data"]["restored_from_version"] == 2

        # Verify live state is now version 6, with spec matching spec_v2
        get_resp = client.get(f"/blueprint.info.get?blueprint_id={blueprint_id}")
        assert get_resp.status_code == 200
        live_doc = get_resp.get_json()["data"]
        assert live_doc["version"] == 6
        assert live_doc["spec_dict"] == spec_v2

        # Verify version history now has 5 snapshots (versions 5, 4, 3, 2, 1)
        history_resp = client.get(f"/blueprint.versions.list?blueprint_id={blueprint_id}")
        assert history_resp.status_code == 200
        history_data = history_resp.get_json()["data"]
        assert history_data["total"] == 5
        versions = [item["version"] for item in history_data["items"]]
        assert versions == [5, 4, 3, 2, 1]
        assert history_data["items"][0]["change_summary"] == "Restored to version 2"

    def test_concurrent_modification_prevention(self, client, service):
        """
        Test that concurrent modifications (OCC) prevent overwriting.
        If Request B loads version 1 but the database has already been updated to version 2,
        Request B's update should fail with a 409 Conflict.
        """
        # 1. Create a new workflow (blueprint) - Version 1
        identity_data = {"type": "user", "id": "u-bob"}
        spec_v1 = {"name": "OCC Workflow", "description": "Initial draft", "plan": []}
        
        save_resp = client.post(
            "/blueprint.save",
            json={"identity": identity_data, "spec_dict": spec_v1}
        )
        assert save_resp.status_code == 201
        blueprint_id = save_resp.get_json()["data"]["blueprint_id"]

        # 2. User A updates the workflow (v1 -> v2)
        spec_a = {"name": "OCC Workflow", "description": "User A update", "plan": []}
        update_resp_a = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_a,
                "change_summary": "User A edit",
                "user_id": "u-alice",
            }
        )
        assert update_resp_a.status_code == 200

        # 3. Now, simulate User B who has a stale view of the document (still thinks it is version 1).
        # We can do this by patching the service's load method to return version 1.
        from unittest.mock import patch
        from lib.mas.blueprints.models.blueprint import BlueprintDocument
        from datetime import datetime, timezone

        stale_doc = BlueprintDocument(
            blueprint_id=blueprint_id,
            identity=identity_data,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            spec_dict=spec_v1,
            rid_refs=[],
            metadata={},
            version=1, # Stale version!
        )

        with patch.object(service, "_load_document_or_raise", return_value=stale_doc):
            spec_b = {"name": "OCC Workflow", "description": "User B update", "plan": []}
            update_resp_b = client.put(
                "/blueprint.update",
                json={
                    "blueprint_id": blueprint_id,
                    "spec_dict": spec_b,
                    "change_summary": "User B edit",
                    "user_id": "u-charlie",
                }
            )
            # Should fail with 409 Conflict because the database is actually at version 2,
            # but User B's request tried to update expecting version 1.
            assert update_resp_b.status_code == 409
            assert update_resp_b.get_json()["success"] is False
            assert "Concurrent modification conflict" in update_resp_b.get_json()["error"]
        update_resp_a = client.put(
            "/blueprint.update",
            json={
                "blueprint_id": blueprint_id,
                "spec_dict": spec_a,
                "change_summary": "User A edit",
                "user_id": "u-alice",
            }
        )
        assert update_resp_a.status_code == 200

        # 4. User B tries to update the workflow based on stale version 1
        # Wait, how does the update endpoint detect concurrent modification?
        # Let's check if the update endpoint accepts a version or if it checks the database's current version.
        # Let's read the updateBlueprint and update_draft implementation to see how OCC is implemented.
