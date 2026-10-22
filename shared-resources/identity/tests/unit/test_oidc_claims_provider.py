"""Unit tests: ``oidc-claims`` directory provider (fake tokens, no network)."""

import base64
import json
import logging
from types import SimpleNamespace

import pytest

from directory.factory import build_directory_provider
from directory.models import OidcClaimsConfig
from directory.oidc_claims_provider import OidcClaimsDirectoryProvider, normalize_group
from teams.service import TeamService

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_fake_stores():
    """Shadow the conftest autouse fixture: these tests need no Flask app/Mongo."""


def _b64(obj) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()


def make_token(claims: dict) -> str:
    return f"{_b64({'alg': 'none'})}.{_b64(claims)}.sig"


def provider(**kw) -> OidcClaimsDirectoryProvider:
    return OidcClaimsDirectoryProvider(OidcClaimsConfig(**kw))


def ids(groups):
    return [g.group_id for g in groups]


class TestNormalize:
    def test_strips_leading_slash_and_whitespace(self):
        assert normalize_group(" /team-a ") == "team-a"

    def test_subgroup_keeps_inner_separator(self):
        assert normalize_group("/org/team-a") == "org/team-a"

    def test_prefix_removed_after_slash(self):
        assert normalize_group("/app-team-a", prefix="app-") == "team-a"

    def test_case_preserved_by_default_lowercase_optional(self):
        assert normalize_group("/Team-A") == "Team-A"
        assert normalize_group("/Team-A", lowercase=True) == "team-a"

    @pytest.mark.parametrize("raw", [None, 3, "", "/", "  ", ["x"]])
    def test_unusable_values(self, raw):
        assert normalize_group(raw) is None


class TestUserGroups:
    def test_groups_from_claim(self):
        p = provider()
        p.set_user_token(make_token(
            {"preferred_username": "alice", "groups": ["/agent_demo", "/ops"]}
        ))
        assert ids(p.get_user_groups("alice")) == ["agent_demo", "ops"]

    def test_claim_absent(self):
        p = provider()
        p.set_user_token(make_token({"preferred_username": "alice"}))
        assert p.get_user_groups("alice") == []

    def test_claim_malformed(self):
        p = provider()
        p.set_user_token(make_token({"preferred_username": "alice", "groups": {"a": 1}}))
        assert p.get_user_groups("alice") == []

    def test_single_string_claim_and_junk_items_and_dedupe(self):
        p = provider()
        p.set_user_token(make_token(
            {"preferred_username": "alice", "groups": ["/a", "a", 5, None, ""]}
        ))
        assert ids(p.get_user_groups("alice")) == ["a"]
        p.set_user_token(make_token({"preferred_username": "alice", "groups": "/solo"}))
        assert ids(p.get_user_groups("alice")) == ["solo"]

    def test_custom_claim_and_nested_path(self):
        p = provider(claim="realm_access.roles")
        p.set_user_token(make_token(
            {"preferred_username": "alice", "realm_access": {"roles": ["r1"]}}
        ))
        assert ids(p.get_user_groups("alice")) == ["r1"]

    def test_exact_dotted_claim_name_wins(self):
        p = provider(claim="a.b")
        p.set_user_token(make_token({"preferred_username": "alice", "a.b": ["x"]}))
        assert ids(p.get_user_groups("alice")) == ["x"]

    def test_prefix_and_lowercase_config(self):
        p = provider(group_prefix="kc-", lowercase=True)
        p.set_user_token(make_token({"preferred_username": "alice", "groups": ["/kc-Ops"]}))
        assert ids(p.get_user_groups("alice")) == ["ops"]

    def test_token_missing(self):
        assert provider().get_user_groups("alice") == []

    @pytest.mark.parametrize("bad", ["garbage", "a.b.c", "a." + _b64([1]) + ".c"])
    def test_malformed_token(self, bad):
        p = provider()
        p.set_user_token(bad)
        assert p.get_user_groups("alice") == []

    def test_token_of_other_user_is_ignored(self):
        p = provider()
        p.set_user_token(make_token({"preferred_username": "bob", "groups": ["/ops"]}))
        assert p.get_user_groups("alice") == []

    def test_token_is_per_thread(self):
        import threading

        p = provider()
        p.set_user_token(make_token({"preferred_username": "alice", "groups": ["/ops"]}))
        out = []
        t = threading.Thread(target=lambda: out.append(p.get_user_groups("alice")))
        t.start(); t.join()
        assert out == [[]]


class TestGroupLookups:
    @pytest.fixture
    def p(self):
        p = provider()
        p.set_user_token(make_token(
            {"preferred_username": "alice", "groups": ["/agent_demo", "/ops"]}
        ))
        return p

    def test_get_group_present_normalised(self, p):
        assert p.get_group("/agent_demo").group_id == "agent_demo"
        assert p.get_group("agent_demo").members == []

    def test_get_group_absent(self, p):
        assert p.get_group("other") is None

    def test_search_groups_only_callers_groups(self, p):
        assert ids(p.search_groups("DEMO")) == ["agent_demo"]
        assert ids(p.search_groups("")) == ["agent_demo", "ops"]

    def test_get_user_current_only(self, p):
        assert p.get_user("alice").username == "alice"
        assert p.get_user("bob") is None


class TestUnsupported:
    def test_search_users_empty_and_logged(self, caplog):
        with caplog.at_level(logging.INFO):
            assert provider().search_users("a") == []
        assert "not supported" in caplog.text

    def test_members_not_authoritative(self):
        assert provider().group_members_authoritative is False

    def test_refresh_group_members_skipped(self):
        class Repo:
            called = False
            def update_group_members(self, *a):
                Repo.called = True
        svc = TeamService(Repo(), directory_provider=provider())
        svc.refresh_group_members([{"group_id": "g", "members": []}])
        assert Repo.called is False


class TestFactory:
    def test_build(self):
        cfg = SimpleNamespace(
            directory_provider="OIDC-Claims",
            directory_oidc_claim="roles",
            directory_oidc_username_claim="email",
            directory_oidc_group_prefix="",
            directory_oidc_lowercase=False,
            directory_oidc_jwks_url="",
            directory_oidc_issuer="",
            directory_oidc_audience="",
        )
        p = build_directory_provider(cfg)
        assert isinstance(p, OidcClaimsDirectoryProvider)
        p.set_user_token(make_token({"email": "a@x", "roles": ["r"]}))
        assert ids(p.get_user_groups("a@x")) == ["r"]


class TestVerifiedMode:
    """With a JWKS URL configured, only correctly signed tokens are trusted."""

    @pytest.fixture
    def keys(self):
        pytest.importorskip("cryptography")
        from cryptography.hazmat.primitives.asymmetric import rsa

        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def _provider(self, verify_key, **kw):
        p = provider(jwks_url="https://idp.example/jwks", **kw)
        p._jwk_client = SimpleNamespace(
            get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=verify_key)
        )
        return p

    def test_valid_signature_accepted(self, keys):
        import jwt

        tok = jwt.encode(
            {"preferred_username": "alice", "groups": ["/ops"], "iss": "https://idp.example"},
            keys, algorithm="RS256",
        )
        p = self._provider(keys.public_key(), issuer="https://idp.example")
        p.set_user_token(tok)
        assert ids(p.get_user_groups("alice")) == ["ops"]

    def test_forged_signature_rejected(self, keys):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        tok = jwt.encode({"preferred_username": "alice", "groups": ["/ops"]}, other, algorithm="RS256")
        p = self._provider(keys.public_key())
        p.set_user_token(tok)
        assert p.get_user_groups("alice") == []

    def test_wrong_issuer_rejected(self, keys):
        import jwt

        tok = jwt.encode(
            {"preferred_username": "alice", "groups": ["/ops"], "iss": "https://evil"},
            keys, algorithm="RS256",
        )
        p = self._provider(keys.public_key(), issuer="https://idp.example")
        p.set_user_token(tok)
        assert p.get_user_groups("alice") == []
