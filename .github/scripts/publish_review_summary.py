#!/usr/bin/env python3
"""Publish pipeline review output to the GitHub Actions job summary."""

from __future__ import annotations

import os
from pathlib import Path


def fence_codeblock(text: str, lang: str = "text") -> str:
    """Wrap text in a fenced code block that survives embedded backticks."""
    max_run = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    fence = "`" * max(3, max_run + 1)
    return f"{fence}{lang}\n{text}\n{fence}\n"


def copy_section(label: str, text: str) -> str:
    if not text.strip():
        return ""
    return (
        f"<details>\n"
        f"<summary>{label}</summary>\n\n"
        f"{fence_codeblock(text)}"
        f"</details>\n\n"
    )


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> None:
    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    arch_text = read_text(Path("arch_review_output.txt"))
    code_text = read_text(Path("code_review_output.txt"))
    full_text = read_text(Path("review_output.txt")) or f"{arch_text}\n\n{code_text}".strip()

    parts: list[str] = []
    if full_text.strip():
        parts.append(copy_section("Copy full review", full_text))
        parts.append("---\n\n")

    parts.append("## Architecture Review\n\n")
    if arch_text.strip():
        parts.append(arch_text)
        if not arch_text.endswith("\n"):
            parts.append("\n")
        parts.append("\n")
        parts.append(copy_section("Copy Architecture Review", arch_text))
    else:
        parts.append("_No output produced._\n\n")

    parts.append("---\n\n")
    parts.append("## Code Review\n\n")
    if code_text.strip():
        parts.append(code_text)
        if not code_text.endswith("\n"):
            parts.append("\n")
        parts.append("\n")
        parts.append(copy_section("Copy Code Review", code_text))
    else:
        parts.append("_No output produced._\n\n")

    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("".join(parts))


if __name__ == "__main__":
    main()
