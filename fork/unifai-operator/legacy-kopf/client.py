"""Thin HTTP client for the UnifAI multiagent (MAS) and RAG APIs.

Authentication: in-cluster calls use the `X-Authenticated-User` header (see README: restrict with a NetworkPolicy).
"""
import os
import re

import requests

MAS_URL = os.environ.get("UNIFAI_MAS_URL", "http://unifai-multiagent-be:8003").rstrip("/")
RAG_URL = os.environ.get("UNIFAI_RAG_URL", "http://unifai-rag-server:13456").rstrip("/")
TIMEOUT = float(os.environ.get("UNIFAI_HTTP_TIMEOUT", "30"))


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


class Api:
    def __init__(self, base, user, team_id=None):
        self.base, self.user, self.team_id = base, user, team_id

    def call(self, method, path, params=None, body=None, ok=(200, 201, 202)):
        params = dict(params or {})
        if self.team_id:
            params.setdefault("teamId", self.team_id)
        r = requests.request(method, f"{self.base}{path}", params=params, json=body, timeout=TIMEOUT,
                             headers={"X-Authenticated-User": self.user})
        try:
            data = r.json()
        except ValueError:
            data = r.text
        if r.status_code not in ok:
            raise ApiError(r.status_code, data)
        return data


def mas(user, team_id=None):
    return Api(MAS_URL, user, team_id)


def rag(user, team_id=None):
    return Api(RAG_URL, user, team_id)


REF_RE = re.compile(r"^\$ref:(llm|provider|tool|retriever|sandbox|condition|agent)/(.+)$")
KIND_CATEGORY = {"llm": "llms", "provider": "providers", "tool": "tools", "retriever": "retrievers",
                 "sandbox": "sandboxes", "condition": "conditions", "agent": "nodes"}
