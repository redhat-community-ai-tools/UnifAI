"""Tests for container runtime health check and graceful stop."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from devtool.domain.models import ContainerStatus, InfraComponent


@pytest.fixture()
def mongo() -> InfraComponent:
    return InfraComponent(
        name="mongo",
        image="mongo:latest",
        ports=["27017:27017"],
        label="MongoDB",
        stop_timeout=30,
    )


@pytest.fixture()
def redis() -> InfraComponent:
    return InfraComponent(
        name="redis",
        image="redis:latest",
        ports=["6379:6379"],
        label="Redis",
    )


class TestVerifyRunning:
    @patch("devtool.adapters.container.base.time.sleep")
    def test_passes_when_container_stays_running(
        self, mock_sleep: MagicMock, mongo: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime.status = MagicMock(return_value=ContainerStatus.RUNNING)

        runtime._verify_running(mongo)

        mock_sleep.assert_called_once_with(2.0)

    @patch("devtool.adapters.container.base.time.sleep")
    def test_raises_when_container_exits(
        self, mock_sleep: MagicMock, mongo: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime.status = MagicMock(return_value=ContainerStatus.STOPPED)
        runtime._get_exit_code = MagicMock(return_value=139)

        with pytest.raises(RuntimeError, match="exited shortly after starting"):
            runtime._verify_running(mongo)

    @patch("devtool.adapters.container.base.time.sleep")
    def test_error_message_includes_exit_code(
        self, mock_sleep: MagicMock, mongo: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime.status = MagicMock(return_value=ContainerStatus.STOPPED)
        runtime._get_exit_code = MagicMock(return_value=139)

        with pytest.raises(RuntimeError, match="exit=139"):
            runtime._verify_running(mongo)

    @patch("devtool.adapters.container.base.time.sleep")
    def test_error_message_includes_log_command(
        self, mock_sleep: MagicMock, mongo: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime.status = MagicMock(return_value=ContainerStatus.STOPPED)
        runtime._get_exit_code = MagicMock(return_value=1)

        with pytest.raises(RuntimeError, match="podman logs mongo"):
            runtime._verify_running(mongo)


class TestStopWithTimeout:
    @patch("devtool.adapters.container.base.SubprocessContainerRuntime._run")
    def test_stop_uses_timeout_when_set(
        self, mock_run: MagicMock, mongo: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime._log_file = None
        runtime.status = MagicMock(return_value=ContainerStatus.RUNNING)

        runtime.stop(mongo)

        mock_run.assert_called_once_with(
            ["podman", "stop", "--time", "30", "mongo"],
        )

    @patch("devtool.adapters.container.base.SubprocessContainerRuntime._run")
    def test_stop_without_timeout(
        self, mock_run: MagicMock, redis: InfraComponent,
    ) -> None:
        from devtool.adapters.container.base import SubprocessContainerRuntime

        runtime = SubprocessContainerRuntime.__new__(SubprocessContainerRuntime)
        runtime._cmd = ["podman"]
        runtime._log_file = None
        runtime.status = MagicMock(return_value=ContainerStatus.RUNNING)

        runtime.stop(redis)

        mock_run.assert_called_once_with(["podman", "stop", "redis"])


class TestDetectRuntimeEnvOverride:
    @patch.dict("os.environ", {"UNIFAI_CONTAINER_RUNTIME": "sudo docker"})
    @patch("devtool.adapters.container.factory.subprocess.run")
    def test_uses_env_var_when_set(self, mock_run: MagicMock) -> None:
        from devtool.adapters.container.factory import ContainerRuntimeFactory

        mock_run.return_value = MagicMock(returncode=0)

        runtime = ContainerRuntimeFactory.create()

        mock_run.assert_called_once_with(
            ["sudo", "docker", "info"], capture_output=True,
        )
        assert runtime._cmd == ["sudo", "docker"]
        assert runtime.runtime_name == "sudo docker"

    @patch.dict("os.environ", {"UNIFAI_CONTAINER_RUNTIME": "sudo docker"})
    @patch("devtool.adapters.container.factory.subprocess.run")
    def test_raises_when_env_var_command_fails(
        self, mock_run: MagicMock,
    ) -> None:
        from devtool.adapters.container.factory import ContainerRuntimeFactory

        mock_run.return_value = MagicMock(returncode=1)

        with pytest.raises(RuntimeError, match="UNIFAI_CONTAINER_RUNTIME"):
            ContainerRuntimeFactory.create()

    @patch.dict("os.environ", {}, clear=False)
    @patch("devtool.adapters.container.factory.shutil.which", return_value=None)
    def test_error_message_mentions_env_var(
        self, mock_which: MagicMock,
    ) -> None:
        from devtool.adapters.container.factory import ContainerRuntimeFactory

        # Remove the env var if present
        import os
        os.environ.pop("UNIFAI_CONTAINER_RUNTIME", None)

        with pytest.raises(RuntimeError, match="UNIFAI_CONTAINER_RUNTIME"):
            ContainerRuntimeFactory.create()


class TestInfraComponentStopTimeout:
    def test_default_stop_timeout_is_none(self) -> None:
        comp = InfraComponent(
            name="test", image="test:latest",
            ports=[], label="Test",
        )
        assert comp.stop_timeout is None

    def test_stop_timeout_is_set(self, mongo: InfraComponent) -> None:
        assert mongo.stop_timeout == 30
