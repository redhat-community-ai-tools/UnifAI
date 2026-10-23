"""The descriptive sheet stored in blueprint metadata (`display`) carries public fields only."""
import pytest

from mas.blueprints.exceptions import InvalidMetadataKeysError
from mas.blueprints.service import validate_client_metadata

GOOD = {
    "title": "Tekos", "displayName": "Tekos", "tileDescription": "Technical assistant",
    "description": "Answers from the internal documentation.", "icon": "code", "color": "#0066cc",
    "state": "active", "classification": "C2", "maintainer": "platform team",
    "tasks": [{"name": "write-code", "title": "Write code"}],
}


def test_a_public_sheet_is_accepted():
    validate_client_metadata({"display": GOOD})
    validate_client_metadata({"display": {"title": "x"}, "usageScope": "private"})


@pytest.mark.parametrize("hidden", [
    "system_prompt", "system_message", "allowed_tools", "allowed_knowledge", "local_only_for",
    "quota_class", "access_groups", "groups", "digest", "signature", "retrieval",
])
def test_hidden_fields_are_refused(hidden):
    with pytest.raises(InvalidMetadataKeysError):
        validate_client_metadata({"display": {**GOOD, hidden: "x"}})


def test_hidden_fields_are_refused_inside_a_task():
    with pytest.raises(InvalidMetadataKeysError):
        validate_client_metadata({"display": {"tasks": [{"name": "t", "allowed_tools": ["a"]}]}})


@pytest.mark.parametrize("bad", [
    {"title": "<script>alert(1)</script>"}, {"description": "<img src=x>"}, {"title": 3},
    {"title": "x" * 201}, {"icon": "https://evil.example/i.png"}, {"icon": "../x"},
    {"color": "url(http://evil)"}, {"color": "#12"}, {"tasks": "all"}, {"tasks": [{"title": "<b>x"}]},
    {"tasks": [{"name": str(i)} for i in range(21)]},
])
def test_unsafe_values_are_refused(bad):
    with pytest.raises(InvalidMetadataKeysError):
        validate_client_metadata({"display": bad})


def test_display_must_be_an_object():
    with pytest.raises(InvalidMetadataKeysError):
        validate_client_metadata({"display": "Tekos"})


def test_markdown_without_raw_html_is_accepted():
    validate_client_metadata({"display": {"description": "Uses **docs** and `git`; 1 < 2 is fine"}})
