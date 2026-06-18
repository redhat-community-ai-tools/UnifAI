#!/usr/bin/env python3
"""Evaluate code-review and architecture-review output files and gate the CI pipeline."""

import os
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MARKDOWN_BOLD_RE = re.compile(r"\*{1,2}|_{1,2}")
CODE_SCORE_RE = re.compile(r"Code\s+Health\s+Score\b[^\d]*(\d{1,2})\s*/\s*10")
ARCH_VERDICT_RE = re.compile(r"(APPROVE|NEEDS REVISION|REJECT)")


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def strip_markdown(text: str) -> str:
    return MARKDOWN_BOLD_RE.sub("", text)


def parse_code_score(path: Path) -> tuple[int, str]:
    if not path.exists():
        return 0, "file_missing"
    content = path.read_text()
    if not content.strip():
        return 0, "file_empty"

    clean = strip_markdown(strip_ansi(content))
    matches = CODE_SCORE_RE.findall(clean)
    if not matches:
        return 0, "pattern_not_found"

    score = int(matches[-1])
    return score, "ok"


def parse_arch_verdict(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "UNKNOWN", "file_missing"
    content = path.read_text()
    if not content.strip():
        return "UNKNOWN", "file_empty"

    clean = strip_markdown(strip_ansi(content))
    match = ARCH_VERDICT_RE.search(clean)
    if not match:
        return "UNKNOWN", "pattern_not_found"

    return match.group(1), "ok"


def main() -> int:
    threshold = os.environ.get("CODE_REVIEW_THRESHOLD", "8")
    if not threshold.isdigit():
        print(f"::error::CODE_REVIEW_THRESHOLD must be an integer, got '{threshold}'")
        return 1
    threshold = int(threshold)

    code_file = Path(os.environ.get("CODE_REVIEW_FILE", "code_review_output.txt"))
    arch_file = Path(os.environ.get("ARCH_REVIEW_FILE", "arch_review_output.txt"))

    code_score, code_status = parse_code_score(code_file)
    if code_status != "ok":
        print(f"::warning::Could not extract code review score (reason: {code_status}). Check {code_file}.")

    arch_verdict, arch_status = parse_arch_verdict(arch_file)
    if arch_status != "ok":
        print(f"::warning::Could not extract architecture verdict (reason: {arch_status}). Check {arch_file}.")

    arch_pass = arch_verdict == "APPROVE"
    code_pass = code_score >= threshold

    arch_display = "✅ PASS" if arch_pass else f"❌ FAIL ({arch_verdict})"
    code_display = "✅ PASS" if code_pass else "❌ FAIL"

    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    with summary_path.open("a") as summary:
        summary.write("\n---\n\n## Review Gate Results\n\n")
        summary.write("| Review | Result | Threshold | Status |\n")
        summary.write("|--------|--------|-----------|--------|\n")
        summary.write(f"| Architecture Review | {arch_verdict} | APPROVE | {arch_display} |\n")
        summary.write(f"| Code Review | {code_score}/10 | ≥{threshold}/10 | {code_display} |\n\n")

    if not (arch_pass and code_pass):
        print(f"::error::Review gate failed. Architecture: {arch_verdict}, Code: {code_score}/10 (threshold: {threshold})")
        return 1

    with summary_path.open("a") as summary:
        summary.write("✅ **All review gates passed.**\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
