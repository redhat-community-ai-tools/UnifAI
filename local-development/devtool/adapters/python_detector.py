"""Adapter: local Python interpreter detection via PATH and subprocess."""

from __future__ import annotations

import shutil
import subprocess

from devtool.ports.python_resolver import PythonResolver


class LocalPythonResolver(PythonResolver):
    """Discovers Python interpreters on the local filesystem."""

    def find_python(
        self,
        python_min: tuple[int, int],
        python_max: tuple[int, int],
        *,
        env_override: str | None = None,
    ) -> tuple[str, str]:
        candidates = (
            [env_override]
            if env_override
            else ["python3.11", "python3.12", "python3.13", "python3"]
        )

        for candidate in candidates:
            path = shutil.which(candidate)
            if not path:
                if env_override:
                    raise RuntimeError(
                        f"UNIFAI_PYTHON='{env_override}' not found on PATH."
                    )
                continue

            result = self._parse_version(path)
            if result is None:
                if env_override:
                    raise RuntimeError(
                        f"Found Python at {env_override} but could not "
                        f"determine its version."
                    )
                continue
            major, minor, ver_str = result

            if (major, minor) < python_min:
                if env_override:
                    raise RuntimeError(
                        f"{env_override} is Python {ver_str} — too old "
                        f"(need >= {python_min[0]}.{python_min[1]})."
                    )
                continue

            if (major, minor) > python_max:
                if env_override:
                    raise RuntimeError(
                        f"{env_override} is Python {ver_str} — too new "
                        f"(max {python_max[0]}.{python_max[1]}, "
                        f"PyO3 does not support 3.14+)."
                    )
                continue

            minor_str = f"{major}.{minor}"
            return path, minor_str

        raise RuntimeError(
            f"No suitable Python "
            f"({python_min[0]}.{python_min[1]}–{python_max[0]}.{python_max[1]}) "
            f"found. Install one or set UNIFAI_PYTHON."
        )

    @staticmethod
    def _parse_version(python_path: str) -> tuple[int, int, str] | None:
        """Return (major, minor, full_version_string) or None on failure."""
        try:
            out = subprocess.check_output(
                [python_path, "--version"], text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        ver_str = out.split()[-1]
        parts = ver_str.split(".")
        return int(parts[0]), int(parts[1]), ver_str
