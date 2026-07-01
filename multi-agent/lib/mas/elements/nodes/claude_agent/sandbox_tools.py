"""Sandbox-backed replacements for Claude Agent SDK built-in tools.

Creates ``SdkMcpTool`` instances that mirror the built-in Bash, Read,
Write, Edit, Glob, and Grep tools but route all execution through a
``BaseSandbox.exec()`` call.

Activated automatically by ``ClaudeAgentNode._build_options()`` when a
sandbox is attached to the node.
"""

from __future__ import annotations

import logging
import shlex
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

from claude_agent_sdk import SdkMcpTool

if TYPE_CHECKING:
    from mas.elements.sandboxes.common.base_sandbox import BaseSandbox

logger = logging.getLogger(__name__)

DISABLED_BUILTINS: List[str] = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]

BUILTIN_TO_SANDBOX: Dict[str, str] = {
    "Bash": "Bash",
    "Read": "Read",
    "Write": "Write",
    "Edit": "Edit",
    "Glob": "Glob",
    "Grep": "Grep",
}

_MAX_BASH_OUTPUT = 30_000
_DEFAULT_BASH_TIMEOUT_MS = 120_000
_MAX_BASH_TIMEOUT_MS = 600_000
_MAX_READ_LINES = 2_000
_MAX_GLOB_RESULTS = 100
_DEFAULT_GREP_LIMIT = 250
_TOOL_TIMEOUT_SEC = 30


def create_sandbox_mcp_tools(
    sandbox: BaseSandbox,
    skip: Optional[Set[str]] = None,
) -> List[SdkMcpTool]:
    """Create sandbox-backed replacement tools as ``SdkMcpTool`` instances.

    Args:
        sandbox: The configured ``BaseSandbox`` instance.
        skip: Set of tool names to skip (e.g. ``{"Bash"}`` when the user
            explicitly disallowed ``"Bash"``). Pass ``None`` to create all 6.

    Returns:
        List of ``SdkMcpTool`` instances, excluding any in *skip*.
    """
    skip = skip or set()
    builders = [
        ("Bash", _build_bash_tool),
        ("Read", _build_read_tool),
        ("Write", _build_write_tool),
        ("Edit", _build_edit_tool),
        ("Glob", _build_glob_tool),
        ("Grep", _build_grep_tool),
    ]
    tools: List[SdkMcpTool] = []
    for name, builder in builders:
        if name not in skip:
            tools.append(builder(sandbox))
    return tools


# ======================================================================
# Bash
# ======================================================================

def _build_bash_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            command = args["command"]
            timeout_ms = args.get("timeout", _DEFAULT_BASH_TIMEOUT_MS)
            timeout_sec = int(min(timeout_ms / 1000, _MAX_BASH_TIMEOUT_MS / 1000))

            result = sandbox.exec(
                ["bash"], stdin=command.encode("utf-8"),
                timeout_seconds=timeout_sec,
            )

            output = result.stdout or ""
            if result.stderr:
                output += "\n" + result.stderr

            if len(output) > _MAX_BASH_OUTPUT:
                output = output[:_MAX_BASH_OUTPUT] + "\n... (output truncated)"

            if result.exit_code == 0:
                return _text(output.strip() or "(no output)")
            return _error(f"Exit code: {result.exit_code}\n{output.strip()}")
        except Exception as exc:
            logger.warning("sandbox Bash failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Bash",
        description=(
            "Executes a given bash command in a persistent shell session "
            "with optional timeout"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to execute",
                },
                "description": {
                    "type": "string",
                    "description": (
                        "Clear, concise description of what this command "
                        "does in 5-10 words"
                    ),
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout in milliseconds (max 600000)",
                },
            },
            "required": ["command"],
        },
        handler=handler,
    )


# ======================================================================
# Read
# ======================================================================

def _build_read_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = args["file_path"]
            offset = args.get("offset")
            limit = args.get("limit")

            safe_path = shlex.quote(path)
            if offset and limit:
                end = offset + limit - 1
                cmd = (
                    f"awk 'NR>={offset} && NR<={end} "
                    f'{{printf "%6d|%s\\n", NR, $0}}\' {safe_path}'
                )
            elif offset:
                cmd = (
                    f"awk 'NR>={offset} "
                    f'{{printf "%6d|%s\\n", NR, $0}}\' {safe_path}'
                )
            elif limit:
                cmd = (
                    f"awk 'NR<={limit} "
                    f'{{printf "%6d|%s\\n", NR, $0}}\' {safe_path}'
                )
            else:
                cmd = (
                    f"awk '{{printf \"%6d|%s\\n\", NR, $0}}' {safe_path}"
                    f" | head -{_MAX_READ_LINES}"
                )

            result = sandbox.exec(
                ["bash", "-c", cmd], timeout_seconds=_TOOL_TIMEOUT_SEC,
            )

            if result.exit_code != 0:
                error = (
                    result.stderr.strip()
                    or result.stdout.strip()
                    or "File not found"
                )
                return _error(f"Error: {error}")

            content = result.stdout
            if not content.strip():
                return _text("File is empty.")

            return _text(content)
        except Exception as exc:
            logger.warning("sandbox Read failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Read",
        description=(
            "Reads a file from the local filesystem. You can access any "
            "file directly by using this tool."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to read",
                },
                "limit": {
                    "type": "number",
                    "description": (
                        "The number of lines to read. Only provide if the "
                        "file is too large to read at once."
                    ),
                },
                "offset": {
                    "type": "number",
                    "description": (
                        "The line number to start reading from. Only provide "
                        "if the file is too large to read at once"
                    ),
                },
            },
            "required": ["file_path"],
        },
        handler=handler,
    )


# ======================================================================
# Write
# ======================================================================

def _build_write_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = args["file_path"]
            content = args["content"]

            parent = str(PurePosixPath(path).parent)
            cmd = (
                f"mkdir -p {shlex.quote(parent)} "
                f"&& cat > {shlex.quote(path)}"
            )

            result = sandbox.exec(
                ["bash", "-c", cmd],
                stdin=content.encode("utf-8"),
                timeout_seconds=_TOOL_TIMEOUT_SEC,
            )

            if result.exit_code != 0:
                error = result.stderr.strip() or result.stdout.strip()
                return _error(f"Write failed: {error}")

            return _text(f"Successfully wrote to {path}")
        except Exception as exc:
            logger.warning("sandbox Write failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Write",
        description="Writes a file to the local filesystem.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": (
                        "The absolute path to the file to write "
                        "(must be absolute, not relative)"
                    ),
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        },
        handler=handler,
    )


# ======================================================================
# Edit
# ======================================================================

def _build_edit_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            path = args["file_path"]
            old_string = args["old_string"]
            new_string = args["new_string"]
            replace_all = args.get("replace_all", False)

            if old_string == new_string:
                return _error("old_string and new_string are identical")

            read_result = sandbox.exec(
                ["bash", "-c", f"cat {shlex.quote(path)}"],
                timeout_seconds=_TOOL_TIMEOUT_SEC,
            )
            if read_result.exit_code != 0:
                error = read_result.stderr.strip() or "File not found"
                return _error(f"Error: {error}")

            content = read_result.stdout

            count = content.count(old_string)
            if count == 0:
                return _error(f"old_string not found in {path}")
            if count > 1 and not replace_all:
                return _error(
                    f"old_string appears {count} times in {path}, must be "
                    f"unique. Include more surrounding context to make it "
                    f"unique, or set replace_all to true."
                )

            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            write_result = sandbox.exec(
                ["bash", "-c", f"cat > {shlex.quote(path)}"],
                stdin=new_content.encode("utf-8"),
                timeout_seconds=_TOOL_TIMEOUT_SEC,
            )

            if write_result.exit_code != 0:
                error = write_result.stderr.strip() or "Write failed"
                return _error(f"Edit failed: {error}")

            if replace_all:
                return _text(f"Replaced {count} occurrences in {path}")
            return _text(f"Successfully edited {path}")
        except Exception as exc:
            logger.warning("sandbox Edit failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Edit",
        description="Performs exact string replacements in files.",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "The absolute path to the file to modify",
                },
                "old_string": {
                    "type": "string",
                    "description": "The text to replace",
                },
                "new_string": {
                    "type": "string",
                    "description": (
                        "The text to replace it with "
                        "(must be different from old_string)"
                    ),
                },
                "replace_all": {
                    "type": "boolean",
                    "description": (
                        "Replace all occurences of old_string (default false)"
                    ),
                    "default": False,
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
        handler=handler,
    )


# ======================================================================
# Glob
# ======================================================================

def _build_glob_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            pattern = args["pattern"]
            search_path = args.get("path", ".")

            script = (
                "import glob, os\n"
                f"os.chdir({search_path!r})\n"
                f"matches = glob.glob({pattern!r}, recursive=True)\n"
                "matches.sort("
                "key=lambda p: os.path.getmtime(p) "
                "if os.path.exists(p) else 0, reverse=True)\n"
                f"print('\\n'.join(matches[:{_MAX_GLOB_RESULTS}]))\n"
            )

            result = sandbox.exec(
                ["python3"], stdin=script.encode("utf-8"),
                timeout_seconds=_TOOL_TIMEOUT_SEC,
            )

            if result.exit_code != 0:
                safe_pattern = shlex.quote(pattern)
                safe_path = shlex.quote(search_path)
                result = sandbox.exec(
                    ["bash", "-c", (
                        f"find {safe_path} -path {safe_pattern} -type f "
                        f"2>/dev/null | head -{_MAX_GLOB_RESULTS}"
                    )],
                    timeout_seconds=_TOOL_TIMEOUT_SEC,
                )

            output = result.stdout.strip()
            if not output:
                return _text("No files matched the pattern.")
            return _text(output)
        except Exception as exc:
            logger.warning("sandbox Glob failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Glob",
        description=(
            "Fast file pattern matching tool that works with any codebase size"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "The glob pattern to match files against",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "The directory to search in. If not specified, the "
                        "current working directory will be used."
                    ),
                },
            },
            "required": ["pattern"],
        },
        handler=handler,
    )


# ======================================================================
# Grep
# ======================================================================

def _build_grep_tool(sandbox: BaseSandbox) -> SdkMcpTool:
    async def handler(args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            pattern = args["pattern"]
            path = args.get("path", ".")
            glob_filter = args.get("glob")
            type_filter = args.get("type")
            output_mode = args.get("output_mode", "files_with_matches")
            case_insensitive = args.get("-i", False)
            show_line_numbers = args.get("-n", True)
            only_matching = args.get("-o", False)
            after = args.get("-A")
            before = args.get("-B")
            context_lines = args.get("-C") or args.get("context")
            multiline = args.get("multiline", False)
            head_limit = args.get("head_limit", _DEFAULT_GREP_LIMIT)
            offset = args.get("offset", 0)

            cmd_parts = ["rg", "--color=never"]

            if output_mode == "files_with_matches":
                cmd_parts.append("-l")
            elif output_mode == "count":
                cmd_parts.append("-c")
            else:
                if show_line_numbers:
                    cmd_parts.append("-n")
                if only_matching:
                    cmd_parts.append("-o")

            if case_insensitive:
                cmd_parts.append("-i")
            if multiline:
                cmd_parts.extend(["-U", "--multiline-dotall"])
            if glob_filter:
                cmd_parts.extend(["--glob", glob_filter])
            if type_filter:
                cmd_parts.extend(["--type", type_filter])
            if after:
                cmd_parts.extend(["-A", str(after)])
            if before:
                cmd_parts.extend(["-B", str(before)])
            if context_lines:
                cmd_parts.extend(["-C", str(context_lines)])

            cmd_parts.extend(["--", pattern, path])

            cmd = " ".join(shlex.quote(p) for p in cmd_parts)
            if head_limit != 0:
                limit = int(head_limit) if head_limit else _DEFAULT_GREP_LIMIT
                if offset:
                    cmd += (
                        f" | tail -n +{int(offset) + 1} | head -n {limit}"
                    )
                else:
                    cmd += f" | head -n {limit}"

            result = sandbox.exec(
                ["bash", "-c", cmd], timeout_seconds=_TOOL_TIMEOUT_SEC,
            )

            if result.exit_code == 127:
                cmd = _build_grep_fallback(
                    pattern, path, glob_filter, case_insensitive,
                    after, before, context_lines, head_limit,
                )
                result = sandbox.exec(
                    ["bash", "-c", cmd],
                    timeout_seconds=_TOOL_TIMEOUT_SEC,
                )

            output = result.stdout.strip()
            if result.exit_code == 1 and not output:
                return _text("No matches found.")
            if result.exit_code not in (0, 1, 127):
                error = result.stderr.strip() or "Search failed"
                return _error(f"Error: {error}")
            if not output:
                return _text("No matches found.")
            return _text(output)
        except Exception as exc:
            logger.warning("sandbox Grep failed: %s", exc, exc_info=True)
            return _error(f"Sandbox error: {exc}")

    return SdkMcpTool(
        name="Grep",
        description="A powerful search tool built on ripgrep",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": (
                        "The regular expression pattern to search for "
                        "in file contents"
                    ),
                },
                "path": {
                    "type": "string",
                    "description": (
                        "File or directory to search in. Defaults to "
                        "current working directory."
                    ),
                },
                "glob": {
                    "type": "string",
                    "description": (
                        'Glob pattern to filter files (e.g. "*.js", '
                        '"*.{ts,tsx}")'
                    ),
                },
                "type": {
                    "type": "string",
                    "description": (
                        "File type to search (rg --type). Common types: "
                        "js, py, rust, go, java, etc."
                    ),
                },
                "output_mode": {
                    "type": "string",
                    "enum": ["content", "files_with_matches", "count"],
                    "description": (
                        "Output mode. Defaults to files_with_matches."
                    ),
                },
                "-i": {
                    "type": "boolean",
                    "description": "Case insensitive search (rg -i)",
                },
                "-n": {
                    "type": "boolean",
                    "description": (
                        "Show line numbers (rg -n). Defaults to true "
                        "in content mode."
                    ),
                },
                "-o": {
                    "type": "boolean",
                    "description": (
                        "Print only matched parts of each line (rg -o). "
                        "Defaults to false."
                    ),
                },
                "-A": {
                    "type": "number",
                    "description": (
                        "Number of lines to show after each match (rg -A)"
                    ),
                },
                "-B": {
                    "type": "number",
                    "description": (
                        "Number of lines to show before each match (rg -B)"
                    ),
                },
                "-C": {
                    "type": "number",
                    "description": (
                        "Number of lines to show before and after each "
                        "match (rg -C)"
                    ),
                },
                "context": {
                    "type": "number",
                    "description": "Alias for -C",
                },
                "multiline": {
                    "type": "boolean",
                    "description": (
                        "Enable multiline mode where . matches newlines "
                        "(rg -U --multiline-dotall)"
                    ),
                },
                "head_limit": {
                    "type": "number",
                    "description": (
                        "Limit output to first N entries. Defaults to 250. "
                        "Pass 0 for unlimited."
                    ),
                },
                "offset": {
                    "type": "number",
                    "description": (
                        "Skip first N entries before applying head_limit. "
                        "Defaults to 0."
                    ),
                },
            },
            "required": ["pattern"],
        },
        handler=handler,
    )


# ======================================================================
# Helpers
# ======================================================================

def _build_grep_fallback(
    pattern: str,
    path: str,
    glob_filter: Optional[str],
    case_insensitive: bool,
    after: Optional[int],
    before: Optional[int],
    context_lines: Optional[int],
    head_limit: int,
) -> str:
    """Build a POSIX ``grep`` fallback when ``rg`` is not installed."""
    cmd = "grep -rn --color=never"
    if case_insensitive:
        cmd += " -i"
    if glob_filter:
        cmd += f" --include={shlex.quote(glob_filter)}"
    if after:
        cmd += f" -A {after}"
    if before:
        cmd += f" -B {before}"
    if context_lines:
        cmd += f" -C {context_lines}"
    cmd += f" -- {shlex.quote(pattern)} {shlex.quote(path)}"
    if head_limit != 0:
        cmd += f" | head -n {head_limit or _DEFAULT_GREP_LIMIT}"
    return cmd


def _text(text: str) -> Dict[str, Any]:
    """Return a successful MCP tool result."""
    return {"content": [{"type": "text", "text": text}]}


def _error(text: str) -> Dict[str, Any]:
    """Return an error MCP tool result."""
    return {"content": [{"type": "text", "text": text}], "is_error": True}
