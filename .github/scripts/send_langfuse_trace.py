#!/usr/bin/env python3
"""Send the complete pipeline review trace to Langfuse.

Runs as a post-step after the agent and telemetry extraction finish.
Reads review.json, telemetry.json, and pipeline_results.json to create
a Langfuse generation with the full review output, token usage, costs,
and quality scores.  Also appends one item to a Langfuse dataset
(``pipeline-training-data``) mirroring the CSV row from
``collect_training_data.py``.

The generation is attached to the same trace that the hook handler
created (deterministic trace ID seeded by session_id / conversation_id).
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from _scoring import to_int


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        print(f"::warning::Langfuse: Could not parse {path}: {exc}")
        return None
    return data if isinstance(data, dict) else None


def _as_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _attach_scores(langfuse, trace_id: str, pipeline_results: dict) -> None:
    """Attach quality scores from pipeline_results.json."""
    arch_verdict = pipeline_results.get("arch_verdict", "")
    if arch_verdict:
        langfuse.create_score(
            name="arch_verdict",
            value=str(arch_verdict),
            trace_id=trace_id,
            data_type="CATEGORICAL",
            comment="Architecture review verdict",
        )

    code_verdict = pipeline_results.get("code_verdict", "")
    if code_verdict:
        langfuse.create_score(
            name="code_verdict",
            value=str(code_verdict),
            trace_id=trace_id,
            data_type="CATEGORICAL",
            comment="Code review verdict",
        )

    code_score = pipeline_results.get("code_health_score")
    if code_score is not None:
        score_val = _as_float(code_score, default=-1)
        if score_val >= 0:
            langfuse.create_score(
                name="code_health_score",
                value=score_val,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment="Code review health score (0-10)",
            )

    code_findings = pipeline_results.get("code_findings", {})
    files_changed = to_int(pipeline_results.get("files_changed", 1)) or 1
    if isinstance(code_findings, dict):
        from _scoring import compute_deterministic_score
        computed = compute_deterministic_score(code_findings, files_changed)
        langfuse.create_score(
            name="computed_score",
            value=float(computed),
            trace_id=trace_id,
            data_type="NUMERIC",
            comment="Deterministic score from Severity Floor formula",
        )

    for domain, key_prefix in [
        ("code_findings", "code"),
        ("arch_findings", "arch"),
    ]:
        findings = pipeline_results.get(domain, {})
        if not isinstance(findings, dict):
            continue
        for severity in ("critical", "major", "minor", "info"):
            count = findings.get(severity)
            if count is None:
                continue
            count_val = _as_float(count, default=-1)
            if count_val >= 0:
                langfuse.create_score(
                    name=f"{key_prefix}_{severity}_count",
                    value=count_val,
                    trace_id=trace_id,
                    data_type="NUMERIC",
                )


DATASET_NAME = "pipeline-training-data"


def _add_dataset_item(
    langfuse,
    trace_id: str,
    pipeline_results: dict | None,
    telemetry_data: dict | None,
) -> None:
    """Append one item to the Langfuse dataset, mirroring collect_training_data.py."""
    langfuse.create_dataset(
        name=DATASET_NAME,
        description="Per-run pipeline review metrics (auto-populated by CI)",
    )

    pr_number = os.environ.get("PR_NUMBER", "")
    branch = os.environ.get("BRANCH_REF", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")

    pr = pipeline_results or {}
    code_findings = pr.get("code_findings", {})
    arch_findings = pr.get("arch_findings", {})
    if not isinstance(code_findings, dict):
        code_findings = {}
    if not isinstance(arch_findings, dict):
        arch_findings = {}

    item_input = {
        "pr_number": pr_number,
        "branch": branch,
        "files_changed": to_int(pr.get("files_changed"), default=0),
    }

    item_output = {
        "arch_verdict": pr.get("arch_verdict", ""),
        "code_verdict": pr.get("code_verdict", ""),
        "model_score": to_int(pr.get("code_health_score"), default=0),
        "code_findings": {
            sev: to_int(code_findings.get(sev), default=0)
            for sev in ("critical", "major", "minor", "info")
        },
        "arch_findings": {
            sev: to_int(arch_findings.get(sev), default=0)
            for sev in ("critical", "major", "minor", "info")
        },
    }

    telem = telemetry_data or {}
    totals = telem.get("totals", {})
    models = telem.get("models", {})

    item_metadata = {
        "run_id": run_id,
        "arch_model": models.get("arch_judge", ""),
        "code_model": models.get("code_judge", ""),
        "orchestrator_model": models.get("orchestrator", ""),
        "duration_ms": to_int(totals.get("duration_ms"), default=0),
        "cost_usd": round(_as_float(totals.get("estimated_cost_usd")), 4),
    }

    langfuse.create_dataset_item(
        dataset_name=DATASET_NAME,
        input=item_input,
        expected_output=item_output,
        metadata=item_metadata,
        source_trace_id=trace_id,
    )


def main() -> int:
    if not os.environ.get("LANGFUSE_PUBLIC_KEY") or not os.environ.get("LANGFUSE_SECRET_KEY"):
        print("::warning::Langfuse: Missing credentials, skipping trace.")
        return 0

    review_data = _load_json(Path("review.json"))
    if not review_data:
        print("::warning::Langfuse: review.json not available, skipping trace.")
        return 0

    session_id = review_data.get("session_id", "")
    if not session_id:
        print("::warning::Langfuse: No session_id in review.json, cannot correlate trace.")
        return 0

    telemetry_data = _load_json(Path("telemetry.json"))
    pipeline_results = _load_json(
        Path(os.environ.get("PIPELINE_RESULTS_JSON", "/tmp/pipeline_results.json"))
    )

    result_text = review_data.get("result", "")
    usage = review_data.get("usage", {})
    if not isinstance(usage, dict):
        usage = {}
    duration_ms = to_int(review_data.get("duration_ms"))
    model = review_data.get("model", "")
    request_id = review_data.get("request_id", "")
    is_error = bool(review_data.get("is_error"))

    try:
        from langfuse import Langfuse, propagate_attributes

        langfuse = Langfuse()
        trace_id = langfuse.create_trace_id(seed=session_id)

        pr_number = os.environ.get("PR_NUMBER", "")
        branch = os.environ.get("BRANCH_REF", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")

        tags = ["pipeline", "ci", "post-step"]
        if pr_number:
            tags.append(f"pr-{pr_number}")
        if is_error:
            tags.append("error")

        input_tokens = to_int(usage.get("inputTokens"))
        output_tokens = to_int(usage.get("outputTokens"))
        cache_read = to_int(usage.get("cacheReadTokens"))
        cache_write = to_int(usage.get("cacheWriteTokens"))

        usage_details: dict = {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }
        if cache_read:
            usage_details["cache_read_input_tokens"] = cache_read
        if cache_write:
            usage_details["cache_creation_input_tokens"] = cache_write

        cost_details: dict = {}
        if telemetry_data:
            totals = telemetry_data.get("totals", {})
            cost_usd = _as_float(totals.get("estimated_cost_usd"))
            if cost_usd > 0:
                cost_details["total"] = cost_usd

        output_text = result_text[:50_000] if result_text else ""

        with propagate_attributes(
            user_id="pipeline-ci",
            session_id=session_id,
            tags=tags,
        ):
            with langfuse.start_as_current_observation(
                name="pipeline-review-output",
                as_type="generation",
                model=model or "unknown",
                trace_context={"trace_id": trace_id},
                input={"command": "/pipeline review"},
            ) as gen:
                gen.update(
                    output=output_text,
                    usage_details=usage_details or None,
                    cost_details=cost_details or None,
                    metadata={
                        "request_id": request_id,
                        "duration_ms": duration_ms,
                        "is_error": is_error,
                        "run_id": run_id,
                        "pr_number": pr_number,
                        "branch": branch,
                    },
                )

        if pipeline_results:
            _attach_scores(langfuse, trace_id, pipeline_results)

        _add_dataset_item(langfuse, trace_id, pipeline_results, telemetry_data)

        langfuse.flush()
        print("Langfuse trace and dataset item sent successfully.")

    except Exception as exc:
        print(f"::warning::Langfuse: Failed to send trace: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
