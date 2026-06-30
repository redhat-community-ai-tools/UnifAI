#!/usr/bin/env python3
"""Evaluate code-review and architecture-review output files and gate the CI pipeline.

Supports two scoring paths:
1. PRIMARY: Read /tmp/pipeline_results.json (structured output from orchestrator) and compute
   a deterministic score using the Severity Floor hybrid formula.
2. FALLBACK: Parse review text files for score/verdict patterns (legacy behavior).
"""

import json
import os
import re
import sys
from pathlib import Path

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
MARKDOWN_BOLD_RE = re.compile(r"[*`]{1,2}")
CODE_SCORE_PATTERNS = [
    re.compile(r"Code\s+Health\s+Score\b[^\d]*(\d{1,2})\s*/\s*10"),
    re.compile(r"score\s+of\s+(\d{1,2})\s*/\s*10", re.IGNORECASE),
    re.compile(r"(?:verdict|review|code)[^\n]{0,40}(\d{1,2})\s*/\s*10", re.IGNORECASE),
]
ARCH_VERDICT_RE = re.compile(r"(APPROVE|NEEDS[_ ]REVISION|REJECT)")
PIPELINE_VERDICT_RE = re.compile(r"^`?PIPELINE_(?:ARCH_|CODE_)?VERDICT:\s*(APPROVE|NEEDS_REVISION|REJECT|CLEAN|NEEDS_REFACTORING|MAJOR_CLEANUP|PASS|FAIL)\b", re.MULTILINE)
EXIT_STATUS_RE = re.compile(r"^EXIT_STATUS:\s*(SUCCESS|REVISION_LIMIT|USER_INPUT_REQUIRED|ERROR|SKILL_NOT_FOUND)", re.MULTILINE)


# ---------------------------------------------------------------------------
# Severity Floor Hybrid Formula
# ---------------------------------------------------------------------------

def compute_deterministic_score(code_findings: dict, files_changed: int) -> int:
    """Compute score using the Severity Floor hybrid formula.

    MAJOR/CRITICAL penalties are flat (never diluted by scope).
    MINOR penalties are density-based (diluted by file count, normalized to 5-file baseline).
    """
    critical = code_findings.get("critical", 0)
    major = code_findings.get("major", 0)
    minor = code_findings.get("minor", 0)

    critical_penalty = critical * 3.0
    major_penalty = major * 1.5
    minor_penalty = (minor * 0.5) / max(1, files_changed / 5)

    score = 10 - critical_penalty - major_penalty - minor_penalty
    return max(1, min(10, round(score)))


# ---------------------------------------------------------------------------
# JSON-based scoring (primary path)
# ---------------------------------------------------------------------------

def try_json_scoring(json_path: Path) -> dict | None:
    """Attempt to read pipeline_results.json and compute deterministic scores.

    Returns a dict with arch_verdict, code_score, computed_score, model_score, source
    or None if the JSON file is unavailable.
    """
    if not json_path.exists():
        return None

    try:
        data = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"::warning::Could not parse {json_path}: {e}. Falling back to text parsing.")
        return None

    if not isinstance(data, dict):
        print(f"::warning::{json_path} is not a JSON object. Falling back to text parsing.")
        return None

    arch_verdict = data.get("arch_verdict", "UNKNOWN")
    code_findings = data.get("code_findings", {})
    files_changed = data.get("files_changed", 1)
    model_score = data.get("code_health_score", 0)

    computed_score = compute_deterministic_score(code_findings, files_changed)

    if model_score and abs(computed_score - model_score) >= 2:
        print(
            f"::warning::Score divergence: model reported {model_score}/10, "
            f"formula computed {computed_score}/10 (delta={computed_score - model_score}). "
            f"Using computed score for gate decision."
        )

    return {
        "arch_verdict": arch_verdict,
        "code_score": computed_score,
        "model_score": model_score,
        "computed_score": computed_score,
        "code_findings": code_findings,
        "files_changed": files_changed,
        "source": "json",
    }


# ---------------------------------------------------------------------------
# Text-based scoring (fallback path)
# ---------------------------------------------------------------------------

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

    pv_matches = PIPELINE_VERDICT_RE.findall(clean)
    if pv_matches:
        token = pv_matches[-1]
        if token == "CLEAN":
            return 8, "ok_pipeline_verdict"
        elif token == "NEEDS_REFACTORING":
            return 5, "ok_pipeline_verdict"
        elif token == "MAJOR_CLEANUP":
            return 3, "ok_pipeline_verdict"
        elif token in ("APPROVE", "PASS"):
            return 8, "ok_pipeline_verdict_mapped"
        elif token == "NEEDS_REVISION":
            return 5, "ok_pipeline_verdict_mapped"
        elif token in ("REJECT", "FAIL"):
            return 3, "ok_pipeline_verdict_mapped"
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

    pv_matches = PIPELINE_VERDICT_RE.findall(clean)
    if pv_matches:
        token = pv_matches[-1]
        verdict_map = {"APPROVE": "APPROVE", "NEEDS_REVISION": "NEEDS REVISION", "REJECT": "REJECT"}
        if token not in verdict_map:
            return "UNKNOWN", f"unexpected_arch_verdict_{token.lower()}"
        return verdict_map[token], "ok"

    matches = ARCH_VERDICT_RE.findall(clean)
    if not matches:
        return "UNKNOWN", "pattern_not_found"

    return matches[-1], "ok"


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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    threshold = os.environ.get("CODE_REVIEW_THRESHOLD", "8")
    if not threshold.isdigit():
        print(f"::error::CODE_REVIEW_THRESHOLD must be an integer, got '{threshold}'")
        return 1
    threshold = int(threshold)

    json_path = Path(os.environ.get("PIPELINE_RESULTS_JSON", "/tmp/pipeline_results.json"))
    code_file = Path(os.environ.get("CODE_REVIEW_FILE", "code_review_output.txt"))
    arch_file = Path(os.environ.get("ARCH_REVIEW_FILE", "arch_review_output.txt"))

    # Try JSON-based deterministic scoring first
    json_result = try_json_scoring(json_path)

    if json_result:
        code_score = json_result["code_score"]
        arch_verdict = json_result["arch_verdict"]
        scoring_source = "deterministic_json"
        model_score = json_result["model_score"]
        print(
            f"::notice::Using deterministic scoring from {json_path}. "
            f"Computed={code_score}/10, Model={model_score}/10, "
            f"Files={json_result['files_changed']}, "
            f"Findings={json_result['code_findings']}"
        )
    else:
        # Fallback to text-based parsing
        scoring_source = "text_fallback"
        model_score = None

        code_score, code_status = parse_code_score(code_file)
        if code_status == "pattern_not_found" or code_status.startswith("file_") or code_status.startswith("verdict_not_code_review"):
            print(f"::warning::Could not extract code review score (reason: {code_status}). Check {code_file}.")
        elif code_status == "ok_pipeline_verdict":
            print(f"::notice::Code review score ({code_score}/10) derived from PIPELINE_VERDICT, "
                  f"not an explicit score in the output. Check {code_file}.")
        elif code_status == "ok_pipeline_verdict_mapped":
            print(f"::warning::Code review score ({code_score}/10) derived from non-code-review "
                  f"PIPELINE_VERDICT token (agent used wrong token set). Check {code_file}.")
        elif code_status.startswith("ok_fallback"):
            print(f"::warning::Code review score extracted via fallback pattern ({code_status}). "
                  f"The output may not follow the expected format. Check {code_file}.")

        arch_verdict, arch_status = parse_arch_verdict(arch_file)
        if arch_status != "ok":
            print(f"::warning::Could not extract architecture verdict (reason: {arch_status}). Check {arch_file}.")

    # Check for pipeline errors from text output (always, regardless of scoring source)
    code_exit, _ = parse_exit_status(code_file)
    arch_exit, _ = parse_exit_status(arch_file)

    pipeline_error = False
    if code_exit in ("SKILL_NOT_FOUND", "ERROR"):
        print(f"::error::Code review pipeline errored (EXIT_STATUS: {code_exit}). Check {code_file}.")
        pipeline_error = True
    if arch_exit in ("SKILL_NOT_FOUND", "ERROR"):
        print(f"::error::Architecture review pipeline errored (EXIT_STATUS: {arch_exit}). Check {arch_file}.")
        pipeline_error = True

    arch_pass = arch_verdict == "APPROVE"
    code_pass = code_score >= threshold

    arch_display = "✅ PASS" if arch_pass else f"❌ FAIL ({arch_verdict})"
    code_display = "✅ PASS" if code_pass else "❌ FAIL"

    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    with summary_path.open("a") as summary:
        summary.write("\n---\n\n## Review Gate Results\n\n")
        summary.write(f"**Scoring method:** {scoring_source}\n\n")
        summary.write("| Review | Result | Threshold | Exit Status | Status |\n")
        summary.write("|--------|--------|-----------|-------------|--------|\n")
        summary.write(f"| Architecture Review | {arch_verdict} | APPROVE | {arch_exit} | {arch_display} |\n")
        summary.write(f"| Code Review | {code_score}/10 | ≥{threshold}/10 | {code_exit} | {code_display} |\n\n")
        if model_score is not None and model_score != code_score:
            summary.write(f"_Model self-reported score: {model_score}/10 | Deterministic computed score: {code_score}/10_\n\n")

    output_path = os.environ.get("GITHUB_OUTPUT", "")
    if output_path:
        with Path(output_path).open("a") as out:
            out.write(f"arch_verdict={arch_verdict}\n")
            out.write(f"code_score={code_score}\n")
            out.write(f"scoring_source={scoring_source}\n")

    if pipeline_error:
        return 1

    if not (arch_pass and code_pass):
        print(f"::error::Review gate failed. Architecture: {arch_verdict}, Code: {code_score}/10 (threshold: {threshold})")
        return 1

    with summary_path.open("a") as summary:
        summary.write("✅ **All review gates passed.**\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
