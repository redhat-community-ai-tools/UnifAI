"""Qdrant URL resolution of the memory tool: QDRANT_IP / QDRANT_PORT combinations and explicit override."""
import pytest
from pydantic import ValidationError

from mas.elements.tools.memory.adapters import resolve_qdrant_url
from mas.elements.tools.memory.config import MemoryToolConfig


@pytest.mark.parametrize("env,expected", [
    ({}, "http://0.0.0.0:6333"),
    ({"QDRANT_IP": "qdrant"}, "http://qdrant:6333"),
    ({"QDRANT_IP": "qdrant", "QDRANT_PORT": "6334"}, "http://qdrant:6334"),
    ({"QDRANT_IP": "http://qdrant"}, "http://qdrant:6333"),
    ({"QDRANT_IP": "http://qdrant", "QDRANT_PORT": "tcp://172.30.1.2:6333"}, "http://qdrant:6333"),
    ({"QDRANT_IP": "https://qdrant", "QDRANT_PORT": "tcp://172.30.1.2:6335"}, "https://qdrant:6335"),
    ({"QDRANT_IP": "qdrant:7000", "QDRANT_PORT": "6333"}, "http://qdrant:7000"),
    ({"QDRANT_IP": "http://qdrant:7000/", "QDRANT_PORT": "tcp://172.30.1.2:6333"}, "http://qdrant:7000"),
    ({"QDRANT_PORT": "tcp://172.30.1.2:6333"}, "http://172.30.1.2:6333"),
    ({"QDRANT_IP": "", "QDRANT_PORT": "tcp://172.30.1.2:6333"}, "http://172.30.1.2:6333"),
    ({"QDRANT_IP": "10.0.0.5", "QDRANT_PORT": "6333"}, "http://10.0.0.5:6333"),
    ({"QDRANT_PORT": "6401"}, "http://0.0.0.0:6401"),
])
def test_env_combinations(env, expected):
    assert resolve_qdrant_url(env=env) == expected


def test_explicit_url_overrides_everything():
    env = {"QDRANT_IP": "ignored", "QDRANT_PORT": "garbage"}
    assert resolve_qdrant_url("https://vec.example:6334/", env=env) == "https://vec.example:6334"


@pytest.mark.parametrize("env,var", [
    ({"QDRANT_PORT": "abc"}, "QDRANT_PORT"),
    ({"QDRANT_PORT": "tcp://172.30.1.2"}, "QDRANT_PORT"),
    ({"QDRANT_PORT": "70000"}, "QDRANT_PORT"),
    ({"QDRANT_IP": "ftp://qdrant"}, "QDRANT_IP"),
    ({"QDRANT_IP": "qdrant:notaport"}, "QDRANT_IP"),
    ({"QDRANT_IP": "http://"}, "QDRANT_IP"),
])
def test_invalid_values_name_the_variable(env, var):
    with pytest.raises(ValueError, match=var):
        resolve_qdrant_url(env=env)


def test_invalid_explicit_url():
    with pytest.raises(ValueError, match="qdrant_url"):
        resolve_qdrant_url("qdrant:6333")


def test_config_validates_qdrant_url():
    assert MemoryToolConfig(scope_id="s", qdrant_url="http://qdrant:6333").qdrant_url == "http://qdrant:6333"
    assert MemoryToolConfig(scope_id="s").qdrant_url is None
    with pytest.raises(ValidationError):
        MemoryToolConfig(scope_id="s", qdrant_url="qdrant:6333")
