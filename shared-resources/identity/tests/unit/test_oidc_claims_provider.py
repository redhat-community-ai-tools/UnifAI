"""Unit tests: ``oidc-claims`` directory provider (fake tokens, no network)."""

import logging
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from directory.factory import build_directory_provider
from directory.models import OidcClaimsConfig
from directory.oidc_claims_provider import OidcClaimsDirectoryProvider, normalize_group
from teams.service import TeamService

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_fake_stores():
    """Shadow the conftest autouse fixture: these tests need no Flask app/Mongo."""


ISS = "https://idp.example/realms/demo"
JWKS = "https://idp.example/realms/demo/protocol/openid-connect/certs"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(claims: dict, *, key=KEY, alg: str = "RS256", iss=ISS, exp=3600) -> str:
    body = {"iss": iss, "exp": int(time.time()) + exp, **claims}
    return jwt.encode(body, key, algorithm=alg)


def provider(**kw) -> OidcClaimsDirectoryProvider:
    kw.setdefault("jwks_url", JWKS)
    kw.setdefault("issuer", ISS)
    p = OidcClaimsDirectoryProvider(OidcClaimsConfig(**kw))
    p._jwk_client = SimpleNamespace(
        get_signing_key_from_jwt=lambda _t: SimpleNamespace(key=KEY.public_key())
    )
    return p


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

    @pytest.mark.parametrize("bad", ["garbage", "a.b.c", "a.WzFd.c"])
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
            directory_oidc_jwks_url=JWKS,
            directory_oidc_issuer=ISS,
            directory_oidc_audience="",
        )
        p = build_directory_provider(cfg)
        assert isinstance(p, OidcClaimsDirectoryProvider)
        p._jwk_client = provider()._jwk_client
        p.set_user_token(make_token({"email": "a@x", "roles": ["r"]}))
        assert ids(p.get_user_groups("a@x")) == ["r"]

    @pytest.mark.parametrize("missing", ["directory_oidc_jwks_url", "directory_oidc_issuer"])
    def test_refuses_to_start_without_jwks_or_issuer(self, missing):
        cfg = SimpleNamespace(
            directory_provider="oidc-claims", directory_oidc_claim="groups",
            directory_oidc_username_claim="preferred_username",
            directory_oidc_group_prefix="", directory_oidc_lowercase=False,
            directory_oidc_jwks_url=JWKS, directory_oidc_issuer=ISS,
            directory_oidc_audience="",
        )
        setattr(cfg, missing, "")
        with pytest.raises(ValueError, match="required"):
            build_directory_provider(cfg)

    def test_provider_itself_refuses_without_jwks(self):
        with pytest.raises(ValueError):
            OidcClaimsDirectoryProvider(OidcClaimsConfig(jwks_url="", issuer=ISS))

    def test_jwks_client_is_cached(self):
        p = OidcClaimsDirectoryProvider(OidcClaimsConfig(jwks_url=JWKS, issuer=ISS))
        assert p._jwk_client.jwk_set_cache is not None
        assert p._jwk_client.jwk_set_cache.lifespan == 300


class TestVerification:
    def _groups(self, p, tok):
        p.set_user_token(tok)
        return p.get_user_groups("alice")

    claims = {"preferred_username": "alice", "groups": ["/ops"]}

    def test_valid_token_accepted(self):
        assert ids(self._groups(provider(), make_token(self.claims))) == ["ops"]

    def test_forged_signature_rejected(self):
        assert self._groups(provider(), make_token(self.claims, key=OTHER_KEY)) == []

    def test_expired_rejected(self):
        assert self._groups(provider(), make_token(self.claims, exp=-60)) == []

    def test_missing_exp_rejected(self):
        tok = jwt.encode({"iss": ISS, **self.claims}, KEY, algorithm="RS256")
        assert self._groups(provider(), tok) == []

    def test_wrong_issuer_rejected(self):
        assert self._groups(provider(), make_token(self.claims, iss="https://evil")) == []

    def test_alg_none_rejected(self):
        tok = jwt.encode({"iss": ISS, "exp": int(time.time()) + 60, **self.claims},
                         None, algorithm="none")
        assert self._groups(provider(), tok) == []

    def test_hs256_rejected(self):
        tok = jwt.encode({"iss": ISS, "exp": int(time.time()) + 60, **self.claims},
                         "k" * 32, algorithm="HS256")
        assert self._groups(provider(), tok) == []

    def test_audience_enforced_only_when_configured(self):
        tok = make_token({**self.claims, "aud": "other"})
        assert ids(self._groups(provider(), tok)) == ["ops"]
        assert self._groups(provider(audience="mine"), tok) == []
        ok = make_token({**self.claims, "aud": "mine"})
        assert ids(self._groups(provider(audience="mine"), ok)) == ["ops"]

    def test_jwks_unreachable_fails_closed_and_logs(self, caplog):
        p = provider()

        def boom(_t):
            raise jwt.PyJWKClientConnectionError("unreachable")

        p._jwk_client = SimpleNamespace(get_signing_key_from_jwt=boom)
        with caplog.at_level(logging.WARNING):
            assert self._groups(p, make_token(self.claims)) == []
        assert "token rejected" in caplog.text
