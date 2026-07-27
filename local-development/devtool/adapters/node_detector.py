"""Adapter: local Node.js detection via PATH and subprocess."""

from __future__ import annotations

import shutil
import subprocess

from devtool.ports.node_resolver import NodeResolver


class LocalNodeResolver(NodeResolver):
    """Discovers the Node.js interpreter on the local filesystem."""

    def check_node_js(self, min_major: int) -> tuple[str, str]:
        path = shutil.which("node")
        if not path:
            raise RuntimeError(
                f"Node.js not found on PATH. Install Node.js {min_major}+ "
                f"(https://nodejs.org) or use nvm: 'nvm install {min_major}'"
            )

        try:
            out = subprocess.check_output(
                [path, "--version"], text=True, timeout=10,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            raise RuntimeError(
                f"Found node at {path} but could not determine its version."
            ) from e

        ver_str = out.lstrip("v")
        try:
            major = int(ver_str.split(".")[0])
        except (ValueError, IndexError) as e:
            raise RuntimeError(
                f"Could not parse Node.js version from: {out}"
            ) from e

        if major < min_major:
            raise RuntimeError(
                f"Node.js {out} is too old (requires {min_major}+).\n"
                f"  💡 Tip: run 'nvm install {min_major}' and "
                f"'nvm use {min_major}', or update Node.js globally."
            )

        return path, ver_str
