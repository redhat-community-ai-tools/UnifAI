"""The dev identity provider is never picked silently outside dev mode."""
from types import SimpleNamespace

import pytest

from bootstrap.container import AppContainer

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)


def _build(mode, configured):
    cfg = SimpleNamespace(identity_provider_mode=mode)
    client = SimpleNamespace(configured=configured, _base="http://identity")
    return AppContainer._build_identity_auth_provider(cfg, client)


def test_unconfigured_without_dev_flag_fails_at_startup():
    with pytest.raises(RuntimeError, match="UNIFAI_DEV_MODE"):
        _build("", configured=False)


def test_unconfigured_with_dev_flag_uses_dev_provider(monkeypatch):
    monkeypatch.setenv("UNIFAI_DEV_MODE", "true")
    assert type(_build("", configured=False)).__name__ == "DevIdentityProvider"


def test_configured_auto_mode_uses_pod_provider():
    assert type(_build("", configured=True)).__name__ == "IdentityPodProvider"
