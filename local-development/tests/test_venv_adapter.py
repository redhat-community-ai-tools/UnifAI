"""Tests for devtool.adapters.venv (LocalVenvManager)."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devtool.adapters.venv import LocalVenvManager
from devtool.domain.models import ServiceInfo, ServiceType, VenvConfig, VenvStrategy


def _make_service(
    name: str = "backend",
    *,
    svc_type: ServiceType = ServiceType.PYTHON,
    strategy: VenvStrategy = VenvStrategy.TOML,
    directory: str = "backend",
    commands: list[str] | None = None,
) -> ServiceInfo:
    return ServiceInfo(
        name=name,
        directory=Path(directory),
        type=svc_type,
        launch="echo ok",
        venv=VenvConfig(strategy=strategy, commands=commands or []),
        env_file=None,
        env_entries={},
    )


class TestExists:
    def test_python_venv_exists(self, tmp_path: Path) -> None:
        svc = _make_service()
        (tmp_path / "backend" / "venv" / "bin").mkdir(parents=True)
        (tmp_path / "backend" / "venv" / "bin" / "activate").touch()

        mgr = LocalVenvManager()
        assert mgr.exists(svc, tmp_path) is True

    def test_python_venv_missing(self, tmp_path: Path) -> None:
        svc = _make_service()
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        assert mgr.exists(svc, tmp_path) is False

    def test_node_modules_exists(self, tmp_path: Path) -> None:
        svc = _make_service(svc_type=ServiceType.NODE, strategy=VenvStrategy.NODE)
        (tmp_path / "backend" / "node_modules").mkdir(parents=True)

        mgr = LocalVenvManager()
        assert mgr.exists(svc, tmp_path) is True

    def test_node_modules_missing(self, tmp_path: Path) -> None:
        svc = _make_service(svc_type=ServiceType.NODE, strategy=VenvStrategy.NODE)
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        assert mgr.exists(svc, tmp_path) is False

    def test_strategy_none_always_true(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.NONE)
        mgr = LocalVenvManager()
        assert mgr.exists(svc, tmp_path) is True


class TestVerify:
    def test_skips_node(self, tmp_path: Path) -> None:
        svc = _make_service(svc_type=ServiceType.NODE, strategy=VenvStrategy.NODE)
        mgr = LocalVenvManager()
        mgr.verify(svc, "3.12", tmp_path)

    def test_skips_strategy_none(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.NONE)
        mgr = LocalVenvManager()
        mgr.verify(svc, "3.12", tmp_path)

    def test_raises_when_no_venv(self, tmp_path: Path) -> None:
        svc = _make_service()
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="No venv found"):
            mgr.verify(svc, "3.12", tmp_path)

    @patch("subprocess.run")
    def test_version_match_passes(self, mock_run, tmp_path: Path) -> None:
        svc = _make_service()
        venv_python = tmp_path / "backend" / "venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        mock_run.return_value = MagicMock(stdout="Python 3.12.5\n")

        mgr = LocalVenvManager()
        mgr.verify(svc, "3.12", tmp_path)

    @patch("subprocess.run")
    def test_version_mismatch_raises(self, mock_run, tmp_path: Path) -> None:
        svc = _make_service()
        venv_python = tmp_path / "backend" / "venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        mock_run.return_value = MagicMock(stdout="Python 3.11.9\n")

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="version mismatch"):
            mgr.verify(svc, "3.12", tmp_path)

    @patch("subprocess.run")
    def test_unparsable_output_raises(self, mock_run, tmp_path: Path) -> None:
        svc = _make_service()
        venv_python = tmp_path / "backend" / "venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        mock_run.return_value = MagicMock(stdout="")

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="Could not determine"):
            mgr.verify(svc, "3.12", tmp_path)


class TestCreate:
    def test_strategy_none_does_nothing(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.NONE)
        mgr = LocalVenvManager()
        mgr.create(svc, "python3", tmp_path)

    def test_skips_when_exists_without_force(self, tmp_path: Path) -> None:
        svc = _make_service()
        (tmp_path / "backend" / "venv" / "bin").mkdir(parents=True)
        (tmp_path / "backend" / "venv" / "bin" / "activate").touch()

        mgr = LocalVenvManager()
        mgr._run = MagicMock()
        mgr.create(svc, "python3", tmp_path)

        mgr._run.assert_not_called()

    @patch("shutil.rmtree")
    def test_force_removes_existing(self, mock_rmtree, tmp_path: Path) -> None:
        svc = _make_service()
        venv_dir = tmp_path / "backend" / "venv"
        venv_dir.mkdir(parents=True)
        (venv_dir / "bin").mkdir()
        (venv_dir / "bin" / "activate").touch()
        (tmp_path / "backend" / "pyproject.toml").touch()

        mgr = LocalVenvManager()
        mgr._run = MagicMock()
        mgr.create(svc, "python3", tmp_path, force=True)

        mock_rmtree.assert_called_once_with(venv_dir)

    def test_toml_requires_pyproject(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.TOML)
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="pyproject.toml"):
            mgr.create(svc, "python3", tmp_path, force=True)

    def test_requirements_requires_file(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.REQUIREMENTS)
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="requirements.txt"):
            mgr.create(svc, "python3", tmp_path, force=True)


class TestSync:
    def test_raises_when_no_venv(self, tmp_path: Path) -> None:
        svc = _make_service()
        (tmp_path / "backend").mkdir()

        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="No venv found"):
            mgr.sync(svc, "python3", tmp_path)

    def test_strategy_none_does_nothing(self, tmp_path: Path) -> None:
        svc = _make_service(strategy=VenvStrategy.NONE)
        mgr = LocalVenvManager()
        mgr._run = MagicMock()
        mgr.sync(svc, "python3", tmp_path)
        mgr._run.assert_not_called()


class TestCreateNode:
    @patch("shutil.which", side_effect=lambda cmd: "/usr/bin/pnpm" if cmd == "pnpm" else None)
    def test_prefers_pnpm(self, mock_which) -> None:
        mgr = LocalVenvManager()
        mgr._run = MagicMock()
        mgr._create_node(Path("/fake"), None)
        mgr._run.assert_called_once_with(["pnpm", "install"], Path("/fake"), None)

    @patch("shutil.which", side_effect=lambda cmd: "/usr/bin/npm" if cmd == "npm" else None)
    def test_falls_back_to_npm(self, mock_which) -> None:
        mgr = LocalVenvManager()
        mgr._run = MagicMock()
        mgr._create_node(Path("/fake"), None)
        mgr._run.assert_called_once_with(["npm", "install"], Path("/fake"), None)

    @patch("shutil.which", return_value=None)
    def test_raises_when_no_package_manager(self, mock_which) -> None:
        mgr = LocalVenvManager()
        with pytest.raises(RuntimeError, match="Neither pnpm nor npm"):
            mgr._create_node(Path("/fake"), None)


class TestCreateCustom:
    def test_replaces_python_placeholder(self) -> None:
        svc = _make_service(
            strategy=VenvStrategy.CUSTOM,
            commands=["{python} -m pip install -e ."],
        )
        mgr = LocalVenvManager()
        mgr._run = MagicMock()

        mgr._create_custom(svc, "/usr/bin/python3.12", Path("/fake"), None)

        called_cmd = mgr._run.call_args[0][0]
        assert called_cmd == ["/usr/bin/python3.12", "-m", "pip", "install", "-e", "."]

    def test_handles_quoted_args(self) -> None:
        svc = _make_service(
            strategy=VenvStrategy.CUSTOM,
            commands=['echo "hello world"'],
        )
        mgr = LocalVenvManager()
        mgr._run = MagicMock()

        mgr._create_custom(svc, "python3", Path("/fake"), None)

        called_cmd = mgr._run.call_args[0][0]
        assert called_cmd == ["echo", "hello world"]
