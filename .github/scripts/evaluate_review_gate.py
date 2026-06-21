#!/usr/bin/env python3
"""Evaluate code-review and architecture-review output files and gate the CI pipeline."""

import os
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MARKDOWN_BOLD_RE = re.compile(r"\*{1,2}|_{1,2}")
CODE_SCORE_PATTERNS = [
    re.compile(r"Code\s+Health\s+Score\b[^\d]*(\d{1,2})\s*/\s*10"),
    re.compile(r"score\s+of\s+(\d{1,2})\s*/\s*10", re.IGNORECASE),
    re.compile(r"(?:verdict|review|code)[^\n]{0,40}(\d{1,2})\s*/\s*10", re.IGNORECASE),
]
ARCH_VERDICT_RE = re.compile(r"(APPROVE|NEEDS REVISION|REJECT)")
PIPELINE_VERDICT_RE = re.compile(r"PIPELINE_VERDICT:\s*(APPROVE|NEEDS_REVISION|REJECT|CLEAN|NEEDS_REFACTORING|MAJOR_CLEANUP)")
EXIT_STATUS_RE = re.compile(r"EXIT_STATUS:\s*(SUCCESS|REVISION_LIMIT|USER_INPUT_REQUIRED|ERROR|SKILL_NOT_FOUND)")


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
    for i, pattern in enumerate(CODE_SCORE_PATTERNS):
        matches = pattern.findall(clean)
        if matches:
            source = "ok" if i == 0 else f"ok_fallback_{i}"
            return int(matches[-1]), source

    pv_match = PIPELINE_VERDICT_RE.search(clean)
    if pv_match:
        token = pv_match.group(1)
        if token == "CLEAN":
            return 8, "ok_pipeline_verdict"
        elif token == "NEEDS_REFACTORING":
            return 5, "ok_pipeline_verdict"
        elif token == "MAJOR_CLEANUP":
            return 3, "ok_pipeline_verdict"
        else:
            return 0, f"verdict_not_code_review_{token.lower()}"

    return 0, "pattern_not_found"


def parse_arch_verdict(path: Path) -> tuple[str, str]:
    if not path.exists():
        return "UNKNOWN", "file_missing"
    content = path.read_text()
    if not content.strip():
        return "UNKNOWN", "file_empty"

    clean = strip_markdown(strip_ansi(content))

    pv_match = PIPELINE_VERDICT_RE.search(clean)
    if pv_match:
        token = pv_match.group(1)
        verdict_map = {"APPROVE": "APPROVE", "NEEDS_REVISION": "NEEDS REVISION", "REJECT": "REJECT"}
        return verdict_map.get(token, token), "ok"

    match = ARCH_VERDICT_RE.search(clean)
    if not match:
        return "UNKNOWN", "pattern_not_found"

    return match.group(1), "ok"


def parse_exit_status(path: Path) -> tuple[str, str]:
    """Parse EXIT_STATUS from pipeline output. Returns (status, parse_status)."""
    if not path.exists():
        return "UNKNOWN", "file_missing"
    content = path.read_text()
    if not content.strip():
        return "UNKNOWN", "file_empty"

    clean = strip_markdown(strip_ansi(content))
    matches = EXIT_STATUS_RE.findall(clean)
    if not matches:
        return "UNKNOWN", "pattern_not_found"

    return matches[-1], "ok"


def main() -> int:
    threshold = os.environ.get("CODE_REVIEW_THRESHOLD", "8")
    if not threshold.isdigit():
        print(f"::error::CODE_REVIEW_THRESHOLD must be an integer, got '{threshold}'")
        return 1
    threshold = int(threshold)

    code_file = Path(os.environ.get("CODE_REVIEW_FILE", "code_review_output.txt"))
    arch_file = Path(os.environ.get("ARCH_REVIEW_FILE", "arch_review_output.txt"))

    code_score, code_status = parse_code_score(code_file)
    if code_status == "pattern_not_found" or code_status.startswith("file_") or code_status.startswith("verdict_not_code_review"):
        print(f"::warning::Could not extract code review score (reason: {code_status}). Check {code_file}.")
    elif code_status == "ok_pipeline_verdict":
        print(f"::notice::Code review score ({code_score}/10) derived from PIPELINE_VERDICT, "
              f"not an explicit score in the output. Check {code_file}.")
    elif code_status.startswith("ok_fallback"):
        print(f"::warning::Code review score extracted via fallback pattern ({code_status}). "
              f"The output may not follow the expected format. Check {code_file}.")

    arch_verdict, arch_status = parse_arch_verdict(arch_file)
    if arch_status != "ok":
        print(f"::warning::Could not extract architecture verdict (reason: {arch_status}). Check {arch_file}.")

    code_exit, _ = parse_exit_status(code_file)
    arch_exit, _ = parse_exit_status(arch_file)

    if code_exit in ("SKILL_NOT_FOUND", "ERROR"):
        print(f"::error::Code review pipeline errored (EXIT_STATUS: {code_exit}). Check {code_file}.")
        return 1
    if arch_exit in ("SKILL_NOT_FOUND", "ERROR"):
        print(f"::error::Architecture review pipeline errored (EXIT_STATUS: {arch_exit}). Check {arch_file}.")
        return 1

    arch_pass = arch_verdict == "APPROVE"
    code_pass = code_score >= threshold

    arch_display = "✅ PASS" if arch_pass else f"❌ FAIL ({arch_verdict})"
    code_display = "✅ PASS" if code_pass else "❌ FAIL"

    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    with summary_path.open("a") as summary:
        summary.write("\n---\n\n## Review Gate Results\n\n")
        summary.write("| Review | Result | Threshold | Exit Status | Status |\n")
        summary.write("|--------|--------|-----------|-------------|--------|\n")
        summary.write(f"| Architecture Review | {arch_verdict} | APPROVE | {arch_exit} | {arch_display} |\n")
        summary.write(f"| Code Review | {code_score}/10 | ≥{threshold}/10 | {code_exit} | {code_display} |\n\n")

    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if output_path:
        with Path(output_path).open("a") as out:
            out.write(f"arch_verdict={arch_verdict}\n")
            out.write(f"code_score={code_score}\n")

    if not (arch_pass and code_pass):
        print(f"::error::Review gate failed. Architecture: {arch_verdict}, Code: {code_score}/10 (threshold: {threshold})")
        return 1

    with summary_path.open("a") as summary:
        summary.write("✅ **All review gates passed.**\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
