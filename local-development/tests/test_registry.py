"""Tests for devtool.domain.registry."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from devtool.adapters.registry_loader import YamlRegistryLoader
from devtool.domain.models import ServiceType, VenvStrategy


@pytest.fixture()
def yaml_path(tmp_path: Path) -> Path:
    content = textwrap.dedent("""\
        python:
          min: "3.11"
          max: "3.13"

        infrastructure:
          mongo:
            image: "mongo:latest"
            ports: ["27017:27017"]
            label: "MongoDB"
          redis:
            image: "redis:latest"
            ports: ["6379:6379"]
            label: "Redis"

        services:
          backend:
            directory: "backend"
            port: 8005
            host: "0.0.0.0"
            type: python
            infrastructure: [mongo]
            env_file: ".env"
            venv:
              strategy: "requirements"
            launch: "python -m run.dev"

          worker:
            directory: "backend"
            type: python
            is_primary: false
            infrastructure: [mongo, redis]
            venv:
              strategy: "none"
            launch: "celery worker"

          ui:
            directory: "ui"
            port: 5000
            type: node
            infrastructure: []
            venv:
              strategy: "node"
            launch: "npm start"

        groups:
          all: [backend, worker, ui]
          services: [backend, ui]
          backend-stack: [backend, worker]

        logging:
          directory: "/tmp/test-logs"
    """)
    p = tmp_path / "services.yaml"
    p.write_text(content)
    return p


class TestLocalAuth:
    @pytest.fixture(autouse=True)
    def _clear_local_auth_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("UNIFAI_LOCAL_AUTH", raising=False)

    def test_local_auth_default_true(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        assert reg.local_auth is True

    def test_local_auth_explicit_false(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            local_auth: false

            python:
              min: "3.11"
              max: "3.13"

            infrastructure: {}

            services:
              backend:
                directory: "backend"
                port: 8005
                type: python
                infrastructure: []
                venv:
                  strategy: "none"
                launch: "echo ok"

            groups:
              all: [backend]
        """)
        p = tmp_path / "services_la_false.yaml"
        p.write_text(content)
        reg = YamlRegistryLoader.load(p)
        assert reg.local_auth is False

    def test_local_auth_explicit_true(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            local_auth: true

            python:
              min: "3.11"
              max: "3.13"

            infrastructure: {}

            services:
              backend:
                directory: "backend"
                port: 8005
                type: python
                infrastructure: []
                venv:
                  strategy: "none"
                launch: "echo ok"

            groups:
              all: [backend]
        """)
        p = tmp_path / "services_la_true.yaml"
        p.write_text(content)
        reg = YamlRegistryLoader.load(p)
        assert reg.local_auth is True

    def test_env_var_overrides_yaml_true(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        content = textwrap.dedent("""\
            local_auth: true

            python:
              min: "3.11"
              max: "3.13"

            infrastructure: {}

            services:
              backend:
                directory: "backend"
                port: 8005
                type: python
                infrastructure: []
                venv:
                  strategy: "none"
                launch: "echo ok"

            groups:
              all: [backend]
        """)
        p = tmp_path / "services_env_override.yaml"
        p.write_text(content)
        monkeypatch.setenv("UNIFAI_LOCAL_AUTH", "false")
        reg = YamlRegistryLoader.load(p)
        assert reg.local_auth is False

    def test_env_var_overrides_yaml_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        content = textwrap.dedent("""\
            local_auth: false

            python:
              min: "3.11"
              max: "3.13"

            infrastructure: {}

            services:
              backend:
                directory: "backend"
                port: 8005
                type: python
                infrastructure: []
                venv:
                  strategy: "none"
                launch: "echo ok"

            groups:
              all: [backend]
        """)
        p = tmp_path / "services_env_override2.yaml"
        p.write_text(content)
        monkeypatch.setenv("UNIFAI_LOCAL_AUTH", "true")
        reg = YamlRegistryLoader.load(p)
        assert reg.local_auth is True

    def test_local_auth_does_not_modify_env_entries(self, tmp_path: Path) -> None:
        content = textwrap.dedent("""\
            local_auth: true

            python:
              min: "3.11"
              max: "3.13"

            infrastructure: {}

            services:
              identity:
                directory: "shared-resources/identity"
                port: 13456
                type: python
                infrastructure: []
                env_file: ".env"
                env_entries:
                  keycloak_base_url: "https://keycloak.test"
                  client_id: "<REPLACE>"
                  client_secret: "<REPLACE>"
                venv:
                  strategy: "none"
                launch: "echo ok"

            groups:
              all: [identity]
        """)
        p = tmp_path / "services_la_entries.yaml"
        p.write_text(content)
        reg = YamlRegistryLoader.load(p)
        svc = reg.get_service("identity")
        assert "keycloak_base_url" in svc.env_entries
        assert "client_id" in svc.env_entries
        assert "client_secret" in svc.env_entries


class TestRegistryLoading:
    def test_loads_services(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        assert reg.service_names() == ["backend", "worker", "ui"]

    def test_loads_infrastructure(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        mongo = reg.get_infra("mongo")
        assert mongo.image == "mongo:latest"
        assert mongo.ports == ["27017:27017"]
        assert mongo.label == "MongoDB"

    def test_python_bounds(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        assert reg.python_bounds() == ((3, 11), (3, 13))

    def test_log_dir(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        assert reg.log_dir == Path("/tmp/test-logs")


class TestServiceParsing:
    def test_service_fields(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        svc = reg.get_service("backend")
        assert svc.directory == Path("backend")
        assert svc.port == 8005
        assert svc.type is ServiceType.PYTHON
        assert svc.infrastructure == ["mongo"]
        assert svc.is_primary is True
        assert svc.venv.strategy is VenvStrategy.REQUIREMENTS
        assert svc.launch == "python -m run.dev"

    def test_non_primary_service(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        svc = reg.get_service("worker")
        assert svc.is_primary is False

    def test_node_service(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        svc = reg.get_service("ui")
        assert svc.type is ServiceType.NODE
        assert svc.venv.strategy is VenvStrategy.NODE

    def test_unknown_service_raises(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        with pytest.raises(KeyError, match="Unknown service 'nope'"):
            reg.get_service("nope")


class TestPrimaryServices:
    def test_deduplicates_by_directory(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        primaries = reg.primary_services()
        names = [s.name for s in primaries]
        assert "backend" in names
        assert "ui" in names
        assert "worker" not in names


class TestResolveServices:
    def test_expand_group(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        resolved = reg.resolve_services(["services"])
        assert [s.name for s in resolved] == ["backend", "ui"]

    def test_mix_service_and_group(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        resolved = reg.resolve_services(["worker", "services"])
        names = [s.name for s in resolved]
        assert names == ["worker", "backend", "ui"]

    def test_deduplicates(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        resolved = reg.resolve_services(["backend", "all"])
        names = [s.name for s in resolved]
        assert names.count("backend") == 1

    def test_unknown_target_raises(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        with pytest.raises(KeyError):
            reg.resolve_services(["nonexistent"])


class TestInfraForServices:
    def test_union_of_infra(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        services = reg.resolve_services(["backend-stack"])
        infra = reg.infra_for_services(services)
        names = [c.name for c in infra]
        assert "mongo" in names
        assert "redis" in names
        assert len(names) == 2

    def test_no_duplicates(self, yaml_path: Path) -> None:
        reg = YamlRegistryLoader.load(yaml_path)
        services = reg.resolve_services(["all"])
        infra = reg.infra_for_services(services)
        names = [c.name for c in infra]
        assert len(names) == len(set(names))
