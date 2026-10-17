"""Confluence Cloud/Data Center REST connector (content API v1).

Scope of a source: one space, optionally narrowed to the subtree under a root
page found by title. Pages are listed with CQL and followed through
`_links.next` (offset paging does not advance for `ancestor=` queries).
"""
from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

_EXPAND = "body.storage,version,ancestors,metadata.labels"


@dataclass(frozen=True)
class ConfluencePage:
    page_id: str
    title: str
    version: int
    last_modified: str
    url: str
    html: str
    ancestors: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)


class ConfluenceError(RuntimeError):
    pass


class ConfluenceConnector:
    def __init__(self, base_url: str, username: str = "", token: str = "", verify_tls: bool = True,
                 timeout: float = 30.0, page_size: int = 25, session: requests.Session | None = None) -> None:
        self._base = base_url.rstrip("/")
        # Confluence Cloud serves the API under /wiki; Data Center under the base URL's own context path.
        cloud = ".atlassian.net" in self._base and not self._base.endswith("/wiki")
        self._api = f"{self._base}/wiki/rest/api" if cloud else f"{self._base}/rest/api"
        self._session = session or requests.Session()
        self._session.verify = verify_tls
        if username and token:
            self._session.auth = (username, token)
        elif token:
            self._session.headers["Authorization"] = f"Bearer {token}"
        self._timeout = timeout
        self._page_size = page_size

    def _get(self, url: str, params: dict | None = None) -> dict:
        resp = self._session.get(url, params=params, timeout=self._timeout)
        if resp.status_code >= 400:
            raise ConfluenceError(f"Confluence {resp.status_code} on {url}: {resp.text[:200]}")
        return resp.json()

    def _search(self, cql: str) -> Iterator[dict]:
        url: str | None = f"{self._api}/content/search"
        params: dict | None = {"cql": cql, "limit": self._page_size, "expand": _EXPAND}
        while url:
            data = self._get(url, params)
            yield from data.get("results", [])
            nxt = (data.get("_links") or {}).get("next")
            # `next` is relative to the API context path (/wiki on Cloud); `_links.base` carries it.
            base = ((data.get("_links") or {}).get("base") or self._api.rsplit("/rest/api", 1)[0]).rstrip("/")
            url = base + nxt if nxt else None
            params = None  # the next link carries the query

    def find_page_id(self, space_key: str, title: str) -> str | None:
        for page in self._search(f'space="{_q(space_key)}" and type=page and title="{_q(title)}"'):
            return str(page["id"])
        return None

    def iter_pages(self, space_key: str, root_title: str = "", exclude_labels: Sequence[str] = ()) -> Iterator[ConfluencePage]:
        excluded = {lbl.lower() for lbl in exclude_labels}
        cql = f'space="{_q(space_key)}" and type=page'
        root_id = self.find_page_id(space_key, root_title) if root_title else None
        if root_title and not root_id:
            raise ConfluenceError(f"root page {root_title!r} not found in space {space_key}")
        queries = [f"id={root_id}", f"ancestor={root_id} and type=page"] if root_id else [cql]
        seen = set()
        for query in queries:
            for raw in self._search(query):
                page = self._page(raw)
                if page.page_id in seen or excluded.intersection(lbl.lower() for lbl in page.labels):
                    continue
                seen.add(page.page_id)
                yield page

    def _page(self, raw: dict) -> ConfluencePage:
        links = raw.get("_links") or {}
        base = (links.get("base") or self._base).rstrip("/")
        return ConfluencePage(
            page_id=str(raw["id"]),
            title=raw.get("title", ""),
            version=int((raw.get("version") or {}).get("number", 0)),
            last_modified=(raw.get("version") or {}).get("when", ""),
            url=base + links.get("webui", f"/pages/{raw['id']}"),
            html=((raw.get("body") or {}).get("storage") or {}).get("value", ""),
            ancestors=[a.get("title", "") for a in raw.get("ancestors") or []],
            labels=[lbl.get("name", "") for lbl in ((raw.get("metadata") or {}).get("labels") or {}).get("results", [])],
        )


def _q(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
