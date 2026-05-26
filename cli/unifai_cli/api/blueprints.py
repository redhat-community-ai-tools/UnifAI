"""Blueprints API — list and inspect workflow blueprints."""
from __future__ import annotations

from typing import List

from unifai_cli.api.base import MASClient


class BlueprintsAPI(MASClient):
    """API methods for workflow blueprints."""

    def list_blueprint_summaries(self, user_id: str) -> List[dict]:
        return self._get(
            "blueprints",
            "available.blueprints.summary.get",
            params={"userId": user_id},
            user_id=user_id,
        )

    def get_blueprint(self, blueprint_id: str) -> dict:
        return self._get("blueprints", "blueprint.info.get",
                         params={"blueprintId": blueprint_id})
