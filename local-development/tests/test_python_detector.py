"""Tests for devtool.adapters.python_detector (LocalPythonResolver)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from devtool.adapters.python_detector import LocalPythonResolver


class TestParseVersion:
    @patch("subprocess.check_output", return_value="Python 3.12.5\n")
    def test_parses_standard_output(self, mock_out) -> None:
        result = LocalPythonResolver._parse_version("/usr/bin/python3")
        assert result == (3, 12, "3.12.5")

    @patch("subprocess.check_output", return_value="Python 3.11.0a1\n")
    def test_parses_prerelease(self, mock_out) -> None:
        major, minor, ver_str = LocalPythonResolver._parse_version("/usr/bin/python3")
        assert major == 3
        assert minor == 11

    @patch("subprocess.check_output", side_effect=FileNotFoundError)
    def test_returns_none_on_missing_binary(self, mock_out) -> None:
        assert LocalPythonResolver._parse_version("/no/python") is None

    @patch("subprocess.check_output", side_effect=subprocess.CalledProcessError(1, "python"))
    def test_returns_none_on_subprocess_error(self, mock_out) -> None:
        assert LocalPythonResolver._parse_version("/bad/python") is None


class TestFindPython:
    @patch("shutil.which", return_value="/usr/bin/python3.12")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 12, "3.12.5"),
    )
    def test_finds_matching_candidate(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        path, minor = resolver.find_python((3, 11), (3, 13))
        assert path == "/usr/bin/python3.12"
        assert minor == "3.12"

    @patch("shutil.which", return_value=None)
    def test_raises_when_no_python_found(self, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="No suitable Python"):
            resolver.find_python((3, 11), (3, 13))

    @patch("shutil.which", return_value="/usr/bin/python3")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 10, "3.10.1"),
    )
    def test_skips_too_old(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="No suitable Python"):
            resolver.find_python((3, 11), (3, 13))

    @patch("shutil.which", return_value="/usr/bin/python3")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 14, "3.14.0"),
    )
    def test_skips_too_new(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="No suitable Python"):
            resolver.find_python((3, 11), (3, 13))

    @patch("shutil.which", return_value="/custom/python")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 12, "3.12.3"),
    )
    def test_env_override_used(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        path, _ = resolver.find_python(
            (3, 11), (3, 13), env_override="/custom/python",
        )
        assert path == "/custom/python"
        mock_which.assert_called_once_with("/custom/python")

    @patch("shutil.which", return_value=None)
    def test_env_override_not_found_raises(self, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="UNIFAI_PYTHON="):
            resolver.find_python(
                (3, 11), (3, 13), env_override="missing-python",
            )

    @patch("shutil.which", return_value="/usr/bin/old-python")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 10, "3.10.0"),
    )
    def test_env_override_too_old_raises(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="too old"):
            resolver.find_python(
                (3, 11), (3, 13), env_override="/usr/bin/old-python",
            )

    @patch("shutil.which", return_value="/usr/bin/new-python")
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 14, "3.14.0"),
    )
    def test_env_override_too_new_raises(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="too new"):
            resolver.find_python(
                (3, 11), (3, 13), env_override="/usr/bin/new-python",
            )

    @patch("shutil.which", return_value="/usr/bin/bad-python")
    @patch.object(LocalPythonResolver, "_parse_version", return_value=None)
    def test_env_override_unparsable_raises(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        with pytest.raises(RuntimeError, match="could not determine"):
            resolver.find_python(
                (3, 11), (3, 13), env_override="/usr/bin/bad-python",
            )

    @patch("shutil.which", side_effect=[None, None, None, "/usr/bin/python3"])
    @patch.object(
        LocalPythonResolver, "_parse_version",
        return_value=(3, 12, "3.12.5"),
    )
    def test_tries_multiple_candidates(self, mock_parse, mock_which) -> None:
        resolver = LocalPythonResolver()
        path, _ = resolver.find_python((3, 11), (3, 13))
        assert path == "/usr/bin/python3"
        assert mock_which.call_count == 4
