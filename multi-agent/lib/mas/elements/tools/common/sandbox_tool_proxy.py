"""Transparent proxy that routes tool execution through the sandbox.

Preserves the inner tool's name / description / schema so the LLM sees
no difference.  No fallback to local execution — if sandbox is
configured, everything runs there.  Errors propagate to the LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import cloudpickle
import openshell.sandbox as _openshell_sandbox

from mas.elements.tools.common.base_tool import BaseTool
import mas.elements.tools.common.sandbox_factories as _sandbox_factories_module
from mas.elements.tools.common.sandbox_factories import call_mcp_tool

cloudpickle.register_pickle_by_value(_sandbox_factories_module)

_openshell_sandbox._SANDBOX_PYTHON_BIN = "python3.12"

logger = logging.getLogger(__name__)

_FACTORY_MAP: Dict[str, Any] = {
    "mcp_proxy": call_mcp_tool,
}

_DEFAULT_TIMEOUT_SECONDS = 300


class SandboxToolProxy(BaseTool):
    """Routes a tool's execution through the sandbox via ``exec_python``.

    The LLM sees the same tool name, description, and input schema.
    Under the hood, the proxy serializes a module-level factory function
    + the tool's serializable config via cloudpickle (handled by the SDK)
    and runs it inside the sandbox container.

    Patches the SDK to use ``python3.12`` instead of the default
    ``python`` to match the worker's Python version and avoid
    cross-version cloudpickle bytecode issues.
    """

    name: str = ""
    description: str = ""
    args_schema = None
    _venv_site_packages: str = ""

    def __init__(self, inner_tool: BaseTool, sandbox: Any) -> None:
        super().__init__()
        self.name = inner_tool.name
        self.description = inner_tool.description
        self.args_schema = inner_tool.args_schema
        self._inner = inner_tool
        self._sandbox = sandbox

    def _resolve_venv_site_packages(self) -> str:
        """Find the sandbox venv's site-packages path (once per sandbox).

        cloudpickle is installed in the sandbox's default Python venv
        (3.14). Since cloudpickle is pure Python, python3.12 can import
        it via PYTHONPATH without reinstalling.
        """
        if SandboxToolProxy._venv_site_packages:
            return SandboxToolProxy._venv_site_packages
        session = self._sandbox._get_or_create_session()
        result = session.exec(
            ["python", "-c", "import cloudpickle,os;print(os.path.dirname(os.path.dirname(cloudpickle.__file__)))"],
            timeout_seconds=30,
        )
        if result.exit_code == 0 and result.stdout.strip():
            SandboxToolProxy._venv_site_packages = result.stdout.strip()
        else:
            SandboxToolProxy._venv_site_packages = "/sandbox/.venv/lib/python3.14/site-packages"
        return SandboxToolProxy._venv_site_packages

    def run(self, *args: Any, **kwargs: Any) -> str:
        """Execute the inner tool inside the sandbox.

        Raises:
            RuntimeError: If the inner tool lacks ``get_sandbox_config``
                or no factory function is registered for its type.
        """
        if not hasattr(self._inner, "get_sandbox_config"):
            raise RuntimeError(
                f"Tool '{self.name}' does not support sandbox execution "
                f"(missing get_sandbox_config). Cannot route through sandbox."
            )

        config = self._inner.get_sandbox_config()
        tool_type = config.pop("_tool_type", "mcp_proxy")
        factory = _FACTORY_MAP.get(tool_type)

        if factory is None:
            raise RuntimeError(
                f"No sandbox factory registered for tool type '{tool_type}'. "
                f"Cannot execute '{self.name}' in sandbox."
            )

        site_packages = self._resolve_venv_site_packages()

        transport_type = config.get("transport_type", "streamable http")
        result = self._sandbox.exec_python(
            factory,
            args=(
                config["mcp_url"],
                config["mcp_tool_name"],
                config["headers"],
                transport_type,
            ),
            kwargs=kwargs,
            env={"PYTHONPATH": site_packages},
            timeout_seconds=_DEFAULT_TIMEOUT_SECONDS,
        )

        if result.exit_code != 0:
            error_detail = result.stderr.strip() or result.stdout.strip()
            if error_detail:
                return f"ERROR: {error_detail}"
            return f"ERROR: sandbox exec failed with exit code {result.exit_code}"
        return result.stdout.strip() or "(no output)"

    def get_args_schema_json(self) -> Any:
        """Delegate to the inner tool's schema."""
        return self._inner.get_args_schema_json()
