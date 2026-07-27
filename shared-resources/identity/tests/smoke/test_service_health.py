"""
Optional smoke: call a *running* identity service (no mocks).

Set ``IDENTITY_SMOKE_URL`` to the backend API base the Flask app uses
(``/api`` included), e.g. ``http://127.0.0.1:13456/api`` for local.

Run:
    IDENTITY_SMOKE_URL="http://127.0.0.1:13456/api" pytest tests/smoke/ -m smoke -q -s
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.smoke


def test_health_get() -> None:
    base = os.environ.get("IDENTITY_SMOKE_URL")
    if not base:
        pytest.skip("Set IDENTITY_SMOKE_URL to the /api base (e.g. http://127.0.0.1:13456/api)")
    url = f"{base.rstrip('/')}/health/"
    r = requests.get(url, timeout=15, verify=bool(int(os.environ.get("TLS_VERIFY", "0"))))
    assert r.status_code == 200, f"{r.status_code} {repr(r.text)[:400]}"
    assert r.json().get("status") == "ok"
