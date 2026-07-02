"""Factory functions for sandbox tool execution.

Each function is module-level (picklable by cloudpickle) and runs
inside the sandbox container.  It receives serializable config from
``get_sandbox_config()`` and the tool-call kwargs from the LLM.

Supports both MCP transport types:
- Streamable HTTP: POST with Accept: text/event-stream, application/json
- SSE: GET to establish stream, extract POST endpoint, send tool call
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import urljoin


def _parse_sse_events(raw: str) -> list:
    """Parse raw SSE text into a list of (event_type, data) tuples."""
    events = []
    current_event = ""
    current_data = []
    for line in raw.splitlines():
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:"):].strip())
        elif line == "" and current_data:
            events.append((current_event, "\n".join(current_data)))
            current_event = ""
            current_data = []
    if current_data:
        events.append((current_event, "\n".join(current_data)))
    return events


def _extract_mcp_content(result: Dict[str, Any]) -> str:
    """Extract text content from an MCP JSON-RPC response object."""
    if "result" in result and "content" in result["result"]:
        content = result["result"]["content"]
        if isinstance(content, list) and content:
            texts = []
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])
                elif isinstance(item, dict):
                    texts.append(json.dumps(item))
                else:
                    texts.append(str(item))
            return "\n".join(texts) if texts else json.dumps(result)
    if "error" in result:
        err = result["error"]
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        return f"ERROR: MCP error — {msg}"
    return json.dumps(result)


def _extract_jsonrpc_from_sse(raw: str) -> str:
    """Extract a JSON-RPC result from SSE-formatted response text."""
    for event_type, data in _parse_sse_events(raw):
        if not data:
            continue
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict) and ("result" in parsed or "error" in parsed):
                return _extract_mcp_content(parsed)
        except (json.JSONDecodeError, KeyError):
            continue
    return raw


def _build_jsonrpc_body(tool_name: str, kwargs: Dict[str, Any]) -> bytes:
    """Build a JSON-RPC 2.0 tools/call request body."""
    body: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {"name": tool_name, "arguments": kwargs},
    }
    return json.dumps(body).encode()


def _mcp_post(
    url: str,
    headers: Dict[str, str],
    body: bytes,
    session_id: Optional[str] = None,
) -> tuple:
    """Send a POST to the MCP endpoint, return (response_body, response_headers)."""
    req_headers = {
        **headers,
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
    }
    if session_id:
        req_headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, method="POST", headers=req_headers, data=body)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode(), resp.headers


def _mcp_initialize(url: str, headers: Dict[str, str]) -> str:
    """Perform the MCP initialize + initialized handshake, return session ID."""
    init_body = json.dumps({
        "jsonrpc": "2.0",
        "method": "initialize",
        "id": 0,
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "unifai-sandbox", "version": "1.0.0"},
        },
    }).encode()

    raw, resp_headers = _mcp_post(url, headers, init_body)
    session_id = resp_headers.get("Mcp-Session-Id", "")

    if not session_id:
        if "text/event-stream" in resp_headers.get("Content-Type", ""):
            session_id = resp_headers.get("Mcp-Session-Id", "")
            for event_type, data in _parse_sse_events(raw):
                if not data:
                    continue
                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, dict):
                        session_id = session_id or parsed.get("sessionId", "")
                except json.JSONDecodeError:
                    pass

    if session_id:
        notif_body = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }).encode()
        try:
            _mcp_post(url, headers, notif_body, session_id=session_id)
        except Exception:
            pass

    return session_id


def _call_streamable_http(
    url: str,
    tool_name: str,
    headers: Dict[str, str],
    **kwargs: Any,
) -> str:
    """MCP Streamable HTTP transport with initialize handshake."""
    session_id = _mcp_initialize(url, headers)

    raw, resp_headers = _mcp_post(
        url,
        headers,
        _build_jsonrpc_body(tool_name, kwargs),
        session_id=session_id,
    )

    content_type = resp_headers.get("Content-Type", "")
    if "text/event-stream" in content_type:
        return _extract_jsonrpc_from_sse(raw)

    result = json.loads(raw)
    return _extract_mcp_content(result)


def _call_sse(
    url: str,
    tool_name: str,
    headers: Dict[str, str],
    **kwargs: Any,
) -> str:
    """MCP SSE transport: GET to open stream, extract POST endpoint, send call.

    The SSE protocol flow:
    1. GET to the SSE endpoint — server holds connection open
    2. Server sends ``event: endpoint`` with a relative URL for POSTing
    3. Client POSTs JSON-RPC to that endpoint
    4. Server sends the response as a ``message`` event on the SSE stream
    """
    endpoint_url: Optional[str] = None
    response_data: Optional[str] = None
    error_holder: list = []

    def _read_sse_stream() -> None:
        nonlocal endpoint_url, response_data
        try:
            req = urllib.request.Request(
                url,
                headers={**headers, "Accept": "text/event-stream"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                buffer = ""
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk.decode()
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        for event_type, data in _parse_sse_events(block):
                            if event_type == "endpoint" and not endpoint_url:
                                endpoint_url = data
                            elif event_type == "message" and data:
                                try:
                                    parsed = json.loads(data)
                                    if isinstance(parsed, dict) and (
                                        "result" in parsed or "error" in parsed
                                    ):
                                        response_data = _extract_mcp_content(parsed)
                                        return
                                except json.JSONDecodeError:
                                    pass
        except Exception as exc:
            error_holder.append(str(exc))

    reader = threading.Thread(target=_read_sse_stream, daemon=True)
    reader.start()

    for _ in range(100):
        if endpoint_url is not None or error_holder:
            break
        reader.join(timeout=0.1)

    if error_holder:
        return f"ERROR: SSE stream failed — {error_holder[0]}"
    if endpoint_url is None:
        return "ERROR: SSE stream did not provide a POST endpoint"

    post_url = urljoin(url, endpoint_url)
    post_req = urllib.request.Request(
        post_url,
        method="POST",
        headers={**headers, "Content-Type": "application/json"},
        data=_build_jsonrpc_body(tool_name, kwargs),
    )
    post_error: str = ""
    try:
        with urllib.request.urlopen(post_req, timeout=120) as resp:
            post_resp = resp.read().decode()
            if post_resp.strip():
                try:
                    return _extract_mcp_content(json.loads(post_resp))
                except json.JSONDecodeError:
                    pass
    except urllib.error.HTTPError as exc:
        post_error = f"HTTP {exc.code} — {exc.read().decode()[:200]}"
    except Exception as exc:
        post_error = f"{type(exc).__name__}: {exc}"

    reader.join(timeout=30)
    if response_data is not None:
        return response_data

    if post_error:
        return f"ERROR: SSE POST failed — {post_error}"
    return "ERROR: No response received from SSE stream"


def call_mcp_tool(
    url: str,
    tool_name: str,
    headers: Dict[str, str],
    transport_type: str = "streamable http",
    **kwargs: Any,
) -> str:
    """Execute an MCP tool call via the configured transport.

    Runs inside the sandbox container using only Python stdlib.
    Dispatches to the appropriate transport handler based on
    the ``transport_type`` parameter.

    Args:
        url: MCP server endpoint.
        tool_name: MCP tool name to invoke.
        headers: HTTP headers including resolved auth.
        transport_type: ``"streamable http"`` or ``"sse"``.
        **kwargs: Tool arguments from the LLM.

    Returns:
        The text content from the MCP response.
    """
    try:
        if transport_type == "sse":
            return _call_sse(url, tool_name, headers, **kwargs)
        return _call_streamable_http(url, tool_name, headers, **kwargs)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode()
        return f"ERROR: HTTP {exc.code} — {error_body}"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}"
