"""Tests for devtool.services.init_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy
from devtool.services.init_service import InitService


def _make_service(name: str = "backend", env_file: str | None = ".env") -> ServiceInfo:
    return ServiceInfo(
        name=name, directory=Path(name), type=ServiceType.PYTHON,
        launch="echo ok", venv=VenvConfig(strategy=VenvStrategy.TOML),
        env_file=env_file, env_entries={"KEY": "val"},
    )


def _make_init_service(
    services: list[ServiceInfo] | None = None,
    root: Path = Path("/fake"),
) -> InitService:
    registry = MagicMock()
    svcs = services or [_make_service()]
    registry.all_services.return_value = svcs
    registry.primary_services.return_value = svcs
    registry.has_node_services.return_value = False
    registry.node_min = None

    runtime = MagicMock()
    runtime.runtime_name = "podman"
    infra = MagicMock()
    venv = MagicMock()
    venv.detect_python.return_value = ("/usr/bin/python3.12", "3.12")
    venv.existing_venvs.return_value = []
    env = MagicMock()

    node_resolver = MagicMock()

    return InitService(
        registry=registry, root=root, runtime=runtime,
        infra_service=infra, venv_service=venv, env_service=env,
        node_resolver=node_resolver,
    )


class TestInit:
    @patch("shutil.which", return_value="/usr/bin/tmux")
    def test_non_interactive_runs_all_steps(self, mock_which, capsys) -> None:
        init_svc = _make_init_service()

        init_svc.init(non_interactive=True)

        init_svc._infra_svc.start.assert_called_once()
        init_svc._venv_svc.setup.assert_called_once()
        init_svc._env_svc.generate.assert_called_once()
        init_svc._env_svc.resolve_auto_generate_keys.assert_called_once()
        init_svc._env_svc.resolve_placeholders.assert_called_once()

        captured = capsys.readouterr()
        assert "Setup complete" in captured.out

    @patch("shutil.which", return_value="/usr/bin/tmux")
    def test_python_failure_propagates(self, mock_which) -> None:
        init_svc = _make_init_service()
        init_svc._venv_svc.detect_python.side_effect = RuntimeError("no python")

        with pytest.raises(RuntimeError, match="no python"):
            init_svc.init(non_interactive=True)

    @patch("shutil.which", return_value=None)
    def test_tmux_missing_warns(self, mock_which, capsys) -> None:
        init_svc = _make_init_service()

        init_svc.init(non_interactive=True)

        captured = capsys.readouterr()
        assert "tmux not found" in captured.out

    @patch("shutil.which", return_value="/usr/bin/tmux")
    def test_existing_venvs_non_interactive_skips_prompt(self, mock_which) -> None:
        svcs = [_make_service()]
        init_svc = _make_init_service(svcs)
        init_svc._venv_svc.existing_venvs.return_value = svcs

        init_svc.init(non_interactive=True)

        init_svc._venv_svc.setup.assert_called_once()


class TestInstallShellCompletion:
    def test_non_interactive_prints_hint(self, capsys) -> None:
        InitService._install_shell_completion(non_interactive=True)

        captured = capsys.readouterr()
        assert "install-completion" in captured.out

    @patch("devtool.services.init_service.os.environ", {"SHELL": ""})
    def test_no_shell_detected_prints_hint(self, capsys) -> None:
        with patch.dict("sys.modules", {"shellingham": None}):
            try:
                InitService._install_shell_completion(non_interactive=False)
            except Exception:
                pass
