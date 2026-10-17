"""Confluence registration: one source = one space, optionally narrowed to a page subtree."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cached_property
from typing import Any

from core.data_sources.domain.model import DataSource
from core.registration.base_registration import BaseRegistration
from core.registration.domain.model import BaseSourceData

# Keys of type_data the pipeline owns; re-registering a source keeps them.
PIPELINE_STATE_KEYS = ("pages", "page_count", "pages_changed", "pages_deleted", "pages_unchanged")


@dataclass
class ConfluenceMetadata:
    source_id: str
    source_name: str
    upload_by: str = ""


class ConfluenceRegistration(BaseRegistration):
    """Registers (or re-registers, idempotently) a Confluence space or subtree."""
    DATA_SOURCE_TYPE = "CONFLUENCE"

    @cached_property
    def source_data(self) -> BaseSourceData:
        base_url = (self.instance.get("baseUrl") or self.instance.get("base_url") or "").rstrip("/")
        space = self.instance.get("spaceKey") or self.instance.get("space_key") or ""
        root = self.instance.get("rootTitle") or self.instance.get("root_title") or ""
        source_id = hashlib.sha256(f"{base_url}|{space}|{root}".encode()).hexdigest()[:24]
        name = self.instance.get("name") or (f"{space}: {root}" if root else space)
        return BaseSourceData(source_id=source_id, source_name=name, pipeline_id=f"confluence_{source_id}",
                              form_data={"base_url": base_url, "space_key": space, "root_title": root,
                                         "exclude_labels": list(self.instance.get("excludeLabels") or [])})

    def run_validator(self) -> tuple[bool, dict[str, Any] | None]:
        form = self.source_data.form_data
        missing = [k for k in ("base_url", "space_key") if not form.get(k)]
        if missing:
            return False, {"source_name": self.source_data.source_name, "issue_type": "MissingField",
                           "message": f"missing {', '.join(missing)}", "validator": "ConfluenceRegistration"}
        if not form["base_url"].startswith(("https://", "http://")):
            return False, {"source_name": self.source_data.source_name, "issue_type": "InvalidUrl",
                           "message": "baseUrl must be an http(s) URL", "validator": "ConfluenceRegistration"}
        return True, None

    def _build_metadata(self) -> ConfluenceMetadata:
        return ConfluenceMetadata(source_id=self.source_data.source_id, source_name=self.source_data.source_name,
                                  upload_by=self.upload_by)

    def _build_type_data(self) -> dict[str, Any]:
        return dict(self.source_data.form_data)

    def _persist(self, type_data: dict[str, Any]) -> None:
        existing = self._data_source_repository.find_by_pipeline_id(self.source_data.pipeline_id)
        if existing is not None and existing.upload_by and existing.upload_by != self.upload_by:
            raise PermissionError(f"source {self.source_data.source_name!r} belongs to {existing.upload_by}")
        state = {k: v for k, v in (existing.type_data if existing else {}).items() if k in PIPELINE_STATE_KEYS}
        now = datetime.now(UTC)
        self._data_source_repository.save(DataSource(
            source_id=self.source_data.source_id,
            source_name=self.source_data.source_name,
            source_type=self.DATA_SOURCE_TYPE,
            pipeline_id=self.source_data.pipeline_id,
            upload_by=self.upload_by,
            created_at=existing.created_at if existing else now,
            last_sync_at=existing.last_sync_at if existing else None,
            tags=self.instance.get("tags", []),
            type_data={**type_data, **state},
            visibility=getattr(self, "_visibility", "private"),
            acl_groups=getattr(self, "_acl_groups", []),
        ))
