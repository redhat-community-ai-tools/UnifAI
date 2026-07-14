"""SDK adapter for creating SandboxClient from in-memory PEM strings."""

import os
import tempfile
from pathlib import Path

from openshell import SandboxClient, TlsConfig


def _write_restricted(path: Path, content: str) -> None:
    """Write a file with 0600 permissions (owner read/write only)."""
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)


def normalize_endpoint(endpoint: str) -> str:
    """Normalize gateway URL to ``host:port`` for gRPC.

    Accepts ``https://host:port``, ``host:port``, or ``host``
    (defaults to port 443).
    """
    ep = endpoint.strip()
    if "://" in ep:
        ep = ep.split("://", 1)[1]
    ep = ep.rstrip("/")
    if ":" not in ep:
        ep = f"{ep}:443"
    return ep


def create_client_from_pem(
    endpoint: str,
    *,
    ca_pem: str,
    cert_pem: str,
    key_pem: str,
    timeout: float = 30.0,
) -> SandboxClient:
    """Create a SandboxClient from in-memory PEM strings.

    The SDK's TlsConfig requires pathlib.Path objects and reads cert
    bytes from disk. In a multi-tenant deployment, each user's PEM
    content is stored in MongoDB as strings.

    This factory writes PEM strings to a TemporaryDirectory, constructs
    the SandboxClient (which reads the bytes and builds the gRPC channel),
    then the context manager deletes the temp files. The gRPC channel
    retains the cert bytes in memory — no files persist on disk.

    Args:
        endpoint: Gateway gRPC endpoint (host:port or https://host:port).
        ca_pem: CA certificate PEM string.
        cert_pem: Client certificate PEM string.
        key_pem: Client private key PEM string.
        timeout: gRPC call timeout in seconds.

    Returns:
        A standard SandboxClient connected via mTLS.
    """
    endpoint = normalize_endpoint(endpoint)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _write_restricted(tmp / "ca.crt", ca_pem)
        _write_restricted(tmp / "tls.crt", cert_pem)
        _write_restricted(tmp / "tls.key", key_pem)

        return SandboxClient(
            endpoint,
            tls=TlsConfig(
                ca_path=tmp / "ca.crt",
                cert_path=tmp / "tls.crt",
                key_path=tmp / "tls.key",
            ),
            timeout=timeout,
        )
