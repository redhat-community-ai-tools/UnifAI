#!/usr/bin/env python3
"""Collect training data from pipeline review runs into a CSV file.

Reads from:
- /tmp/pipeline_results.json (findings, verdicts, scope)
- telemetry.json (cost, duration, models)
- Environment variables (PR number, branch, run ID)

Produces a single CSV row appended to training_data.csv.
"""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from _scoring import compute_deterministic_score

CSV_HEADERS = [
    "run_id",
    "pr_number",
    "branch",
    "timestamp",
    "files_changed",
    "lines_added",
    "lines_removed",
    "arch_verdict",
    "code_verdict",
    "model_score",
    "computed_score",
    "critical_count",
    "major_count",
    "minor_count",
    "info_count",
    "arch_critical",
    "arch_major",
    "arch_minor",
    "arch_info",
    "arch_model",
    "code_model",
    "orchestrator_model",
    "duration_ms",
    "cost_usd",
]


def load_json(path: Path) -> dict | None:
    """Load a JSON file, returning None if missing, unreadable, or not an object."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"::warning::Could not parse {path}: {e}. Skipping.")
        return None
    if not isinstance(data, dict):
        print(f"::warning::{path.name} is not a JSON object, skipping.")
        return None
    return data


_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@")


def _sanitize_csv_value(value) -> str:
    """Prevent CSV injection by escaping formula-triggering prefixes."""
    value = str(value) if value is not None else ""
    if value and value[0] in _CSV_INJECTION_PREFIXES:
        return "'" + value
    return value


def main() -> int:
    json_path = Path(os.environ.get("PIPELINE_RESULTS_JSON", "/tmp/pipeline_results.json"))
    telemetry_path = Path("telemetry.json")
    output_path = Path("training_data.csv")

    pipeline_data = load_json(json_path)
    telemetry_data = load_json(telemetry_path)

    if not pipeline_data:
        print("::warning::Training data: pipeline_results.json not available. Skipping CSV row.")
        return 0

    code_findings = pipeline_data.get("code_findings", {})
    arch_findings = pipeline_data.get("arch_findings", {})
    files_changed = pipeline_data.get("files_changed", 1)
    try:
        files_changed = int(files_changed) if files_changed else 1
    except (TypeError, ValueError):
        print(f"::warning::Training data: files_changed is not numeric ({files_changed!r}). Defaulting to 1.")
        files_changed = 1

    model_score = pipeline_data.get("code_health_score", 0)
    computed_score = compute_deterministic_score(code_findings, files_changed)

    # Extract telemetry data
    duration_ms = 0
    cost_usd = 0.0
    arch_model = ""
    code_model = ""
    orchestrator_model = ""

    if telemetry_data:
        totals = telemetry_data.get("totals", {})
        duration_ms = totals.get("duration_ms", 0)
        cost_usd = totals.get("estimated_cost_usd", 0.0)
        models = telemetry_data.get("models", {})
        arch_model = models.get("arch_judge", "")
        code_model = models.get("code_judge", "")
        orchestrator_model = models.get("orchestrator", "")

    row = {
        "run_id": _sanitize_csv_value(os.environ.get("GITHUB_RUN_ID", "local")),
        "pr_number": _sanitize_csv_value(os.environ.get("PR_NUMBER", "")),
        "branch": _sanitize_csv_value(os.environ.get("BRANCH_REF", "unknown")),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files_changed": files_changed,
        "lines_added": pipeline_data.get("lines_added", 0),
        "lines_removed": pipeline_data.get("lines_removed", 0),
        "arch_verdict": _sanitize_csv_value(pipeline_data.get("arch_verdict", "")),
        "code_verdict": _sanitize_csv_value(pipeline_data.get("code_verdict", "")),
        "model_score": model_score,
        "computed_score": computed_score,
        "critical_count": code_findings.get("critical", 0),
        "major_count": code_findings.get("major", 0),
        "minor_count": code_findings.get("minor", 0),
        "info_count": code_findings.get("info", 0),
        "arch_critical": arch_findings.get("critical", 0),
        "arch_major": arch_findings.get("major", 0),
        "arch_minor": arch_findings.get("minor", 0),
        "arch_info": arch_findings.get("info", 0),
        "arch_model": _sanitize_csv_value(arch_model),
        "code_model": _sanitize_csv_value(code_model),
        "orchestrator_model": _sanitize_csv_value(orchestrator_model),
        "duration_ms": duration_ms,
        "cost_usd": round(cost_usd, 4),
    }

    write_header = not output_path.exists()
    with output_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)

    print(f"Training data row written to {output_path}")
    print(
        f"  PR #{row['pr_number']} | files={files_changed} | "
        f"model_score={model_score} | computed_score={computed_score} | "
        f"findings: C={code_findings.get('critical', 0)} M={code_findings.get('major', 0)} "
        f"m={code_findings.get('minor', 0)} I={code_findings.get('info', 0)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
