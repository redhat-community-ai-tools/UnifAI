"""Resources API — list and inspect inventory resources."""
from __future__ import annotations

from typing import Optional

from unifai_cli.api.base import MASClient


class ResourcesAPI(MASClient):
    """API methods for inventory resources (LLMs, tools, agents, etc.)."""

    def list_resources(self, category: Optional[str] = None,
                       limit: int = 200, offset: int = 0) -> dict:
        params: dict = {"limit": limit, "offset": offset}
        if category:
            params["category"] = category
        return self._get("resources", "resources.list", params=params)

    def get_resource(self, resource_id: str) -> dict:
        return self._get("resources", "resource.get",
                         params={"resourceId": resource_id})
