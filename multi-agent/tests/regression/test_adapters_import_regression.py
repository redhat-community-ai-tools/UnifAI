"""Regression test for ModuleNotFoundError: No module named 'adapters' (GENIE-1336).

This test verifies that bootstrap.container can be imported in a clean
production-like environment where 'adapters' is not on sys.path, but individual
adapter packages ('inbound', 'outbound') are.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import pytest


def test_bootstrap_container_import_without_adapters_on_path():
    """
    Verify that bootstrap.container can be imported without 'adapters' in sys.path.
    
    In a clean installed environment, 'adapters' is not installed as a package,
    but 'inbound' and 'outbound' are. This test simulates that environment by
    creating a temporary directory with symlinks to 'bootstrap', 'outbound',
    'inbound', and 'mas', and running a subprocess with PYTHONPATH set to that
    temporary directory.
    """
    # Arrange: Locate the project root and source directories
    test_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(test_dir, "..", ".."))
    
    bootstrap_dir = os.path.join(project_root, "bootstrap")
    outbound_dir = os.path.join(project_root, "adapters", "outbound")
    inbound_dir = os.path.join(project_root, "adapters", "inbound")
    mas_dir = os.path.join(project_root, "lib", "mas")
    
    # Verify source directories exist
    assert os.path.isdir(bootstrap_dir), f"Bootstrap directory not found at {bootstrap_dir}"
    assert os.path.isdir(outbound_dir), f"Outbound adapters directory not found at {outbound_dir}"
    assert os.path.isdir(inbound_dir), f"Inbound adapters directory not found at {inbound_dir}"
    assert os.path.isdir(mas_dir), f"MAS domain directory not found at {mas_dir}"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create symlinks to simulate the installed package structure
        os.symlink(bootstrap_dir, os.path.join(tmpdir, "bootstrap"))
        os.symlink(outbound_dir, os.path.join(tmpdir, "outbound"))
        os.symlink(inbound_dir, os.path.join(tmpdir, "inbound"))
        os.symlink(mas_dir, os.path.join(tmpdir, "mas"))
        
        # Prepare environment for the subprocess
        env = os.environ.copy()
        env["PYTHONPATH"] = tmpdir
        
        # Act: Run a subprocess to import bootstrap.container
        # We run from a platform-safe temporary directory to ensure the
        # current directory (which contains 'adapters') is not implicitly
        # added to sys.path.
        result = subprocess.run(
            [sys.executable, "-c", "import bootstrap.container"],
            cwd=tempfile.gettempdir(),
            env=env,
            capture_output=True,
            text=True
        )
        
        # Assert: The import should succeed (exit code 0)
        assert result.returncode == 0, (
            f"Failed to import bootstrap.container in a clean environment.\n"
            f"Exit code: {result.returncode}\n"
            f"Stdout: {result.stdout}\n"
            f"Stderr: {result.stderr}"
        )
