"""SDK adapter for creating SandboxClient from in-memory PEM strings."""

import tempfile
from pathlib import Path

from openshell import SandboxClient, TlsConfig


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
        endpoint: Gateway gRPC endpoint (host:port).
        ca_pem: CA certificate PEM string.
        cert_pem: Client certificate PEM string.
        key_pem: Client private key PEM string.
        timeout: gRPC call timeout in seconds.

    Returns:
        A standard SandboxClient connected via mTLS.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "ca.crt").write_text(ca_pem)
        (tmp / "tls.crt").write_text(cert_pem)
        (tmp / "tls.key").write_text(key_pem)

        return SandboxClient(
            endpoint,
            tls=TlsConfig(
                ca_path=tmp / "ca.crt",
                cert_path=tmp / "tls.crt",
                key_path=tmp / "tls.key",
            ),
            timeout=timeout,
        )
