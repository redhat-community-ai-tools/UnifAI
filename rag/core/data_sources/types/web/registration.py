"""Web registration: one source = a few seed URLs of public pages, with optional link discovery."""
from __future__ import annotations

import hashlib
from functools import cached_property
from typing import Any

from core.data_sources.types.confluence.registration import ConfluenceRegistration
from core.registration.domain.model import BaseSourceData

CRAWL_MODES = ("redhat-docs", "generic", "none")


class WebRegistration(ConfluenceRegistration):
    """Registers (or re-registers, idempotently) a set of public web pages.

    Persistence, ownership and the pipeline state kept across re-registration are shared with the
    Confluence source: only the identity and the form fields differ.
    """
    DATA_SOURCE_TYPE = "WEB"

    @cached_property
    def source_data(self) -> BaseSourceData:
        seeds = [u.strip() for u in (self.instance.get("urls") or []) if u and u.strip()]
        source_id = hashlib.sha256("|".join(sorted(seeds)).encode()).hexdigest()[:24]
        name = self.instance.get("name") or (seeds[0] if seeds else "")
        return BaseSourceData(source_id=source_id, source_name=name, pipeline_id=f"web_{source_id}",
                              form_data={"urls": seeds,
                                         "include": list(self.instance.get("include") or []),
                                         "exclude": list(self.instance.get("exclude") or []),
                                         "crawl": self.instance.get("crawl") or "redhat-docs",
                                         "max_pages": int(self.instance.get("maxPages") or 50),
                                         "metadata": dict(self.instance.get("metadata") or {})})

    def run_validator(self) -> tuple[bool, dict[str, Any] | None]:
        form = self.source_data.form_data
        name = self.source_data.source_name

        def refuse(issue: str, message: str) -> tuple[bool, dict[str, Any]]:
            return False, {"source_name": name, "issue_type": issue, "message": message,
                           "validator": "WebRegistration"}

        if not form["urls"]:
            return refuse("MissingField", "missing urls")
        if not all(u.startswith(("https://", "http://")) for u in form["urls"]):
            return refuse("InvalidUrl", "every url must be an http(s) URL")
        if form["crawl"] not in CRAWL_MODES:
            return refuse("InvalidValue", f"crawl must be one of {', '.join(CRAWL_MODES)}")
        return True, None
