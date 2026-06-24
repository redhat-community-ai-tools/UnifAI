#!/usr/bin/env python3
"""Extract token usage telemetry from Cursor CLI JSON output and produce a summary report."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Pricing per 1M tokens (USD) — multi-model Scout + Judge architecture.
# Scout uses a fast model, Judges use flagship/balanced models.
MODEL_PRICING = {
    "claude-4.6-opus-high-thinking": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write": 18.75,
    },
    "claude-4.6-sonnet-medium-thinking": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75,
    },
    "composer-2.5-fast": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.025,
        "cache_write": 0.30,
    },
}

DEFAULT_PRICING = MODEL_PRICING["claude-4.6-sonnet-medium-thinking"]

PHASE_FILES = [
    # Combined review mode: single orchestrator spawns scout + both judges
    ("review", "review.json", "ORCHESTRATOR_MODEL"),
    # Legacy standalone modes (kept for backward compatibility)
    ("arch-review", "arch_review.json", "ARCH_JUDGE_MODEL"),
    ("code-review", "code_review.json", "CODE_JUDGE_MODEL"),
]


def estimate_cost(usage: dict, pricing: dict) -> float:
    """Compute estimated cost in USD from token counts and per-1M-token pricing."""
    input_tokens = usage.get("inputTokens", 0)
    output_tokens = usage.get("outputTokens", 0)
    cache_read = usage.get("cacheReadTokens", 0)
    cache_write = usage.get("cacheWriteTokens", 0)

    cost = (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
        + (cache_read / 1_000_000) * pricing["cache_read"]
        + (cache_write / 1_000_000) * pricing["cache_write"]
    )
    return round(cost, 4)


def format_tokens(count: int) -> str:
    """Format token count for display (e.g., 150000 -> '150K')."""
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)


def parse_phase(phase_name: str, json_path: Path, model: str) -> dict | None:
    """Parse a single phase JSON file and return structured telemetry, or None on failure."""
    if not json_path.exists():
        print(f"::warning::Telemetry: {json_path} not found, skipping phase '{phase_name}'")
        return None

    try:
        data = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        print(f"::warning::Telemetry: Failed to parse {json_path}: {e}")
        return None

    if data.get("is_error") or data.get("type") != "result":
        print(f"::warning::Telemetry: {json_path} indicates an error or non-result type")
        return None

    usage = data.get("usage", {})
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)

    return {
        "name": phase_name,
        "model": model,
        "session_id": data.get("session_id", ""),
        "request_id": data.get("request_id", ""),
        "duration_ms": data.get("duration_ms", 0),
        "usage": {
            "inputTokens": usage.get("inputTokens", 0),
            "outputTokens": usage.get("outputTokens", 0),
            "cacheReadTokens": usage.get("cacheReadTokens", 0),
            "cacheWriteTokens": usage.get("cacheWriteTokens", 0),
        },
        "estimated_cost_usd": estimate_cost(usage, pricing),
    }


def _parse_pr_number(raw: str | None) -> int | None:
    """Safely parse PR_NUMBER env var, returning None if absent or non-numeric."""
    if not raw:
        return None
    try:
        return int(raw) or None
    except ValueError:
        return None


def build_telemetry(phases: list[dict], models: dict[str, str]) -> dict:
    """Build the full telemetry document with totals."""
    totals = {
        "inputTokens": 0,
        "outputTokens": 0,
        "cacheReadTokens": 0,
        "cacheWriteTokens": 0,
        "duration_ms": 0,
        "estimated_cost_usd": 0.0,
    }

    for phase in phases:
        for key in ("inputTokens", "outputTokens", "cacheReadTokens", "cacheWriteTokens"):
            totals[key] += phase["usage"][key]
        totals["duration_ms"] += phase["duration_ms"]
        totals["estimated_cost_usd"] += phase["estimated_cost_usd"]

    totals["estimated_cost_usd"] = round(totals["estimated_cost_usd"], 4)

    return {
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_url": f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', 'unknown')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '0')}",
        "pr_number": _parse_pr_number(os.environ.get("PR_NUMBER")),
        "branch": os.environ.get("BRANCH_REF", "unknown"),
        "models": models,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phases": phases,
        "totals": totals,
    }


def write_summary(telemetry: dict, summary_path: Path) -> None:
    """Append a Markdown summary table to the GitHub Actions step summary."""
    phases = telemetry["phases"]
    totals = telemetry["totals"]

    lines = [
        "",
        "---",
        "",
        "## Token Usage & Cost Summary",
        "",
        "| Phase | Model | Input | Output | Cache Read | Cache Write | Duration | Est. Cost |",
        "|-------|-------|-------|--------|------------|-------------|----------|-----------|",
    ]

    for phase in phases:
        u = phase["usage"]
        duration_s = f"{phase['duration_ms'] / 1000:.0f}s"
        lines.append(
            f"| {phase['name']} | {phase['model']} "
            f"| {format_tokens(u['inputTokens'])} "
            f"| {format_tokens(u['outputTokens'])} "
            f"| {format_tokens(u['cacheReadTokens'])} "
            f"| {format_tokens(u['cacheWriteTokens'])} "
            f"| {duration_s} "
            f"| ${phase['estimated_cost_usd']:.4f} |"
        )

    total_duration = f"{totals['duration_ms'] / 1000:.0f}s"
    lines.append(
        f"| **Total** | | **{format_tokens(totals['inputTokens'])}** "
        f"| **{format_tokens(totals['outputTokens'])}** "
        f"| **{format_tokens(totals['cacheReadTokens'])}** "
        f"| **{format_tokens(totals['cacheWriteTokens'])}** "
        f"| **{total_duration}** "
        f"| **${totals['estimated_cost_usd']:.4f}** |"
    )

    lines.append("")

    with summary_path.open("a") as f:
        f.write("\n".join(lines))


def main() -> int:
    orchestrator_model = os.environ.get("ORCHESTRATOR_MODEL", "claude-4.6-sonnet-medium-thinking")
    resolved_models = {
        "orchestrator": orchestrator_model,
        "scout": os.environ.get("SCOUT_MODEL", "composer-2.5-fast"),
        "arch_judge": os.environ.get("ARCH_JUDGE_MODEL", orchestrator_model),
        "code_judge": os.environ.get("CODE_JUDGE_MODEL", orchestrator_model),
    }

    phases = []
    for phase_name, filename, model_env_var in PHASE_FILES:
        model = os.environ.get(model_env_var, orchestrator_model)
        result = parse_phase(phase_name, Path(filename), model)
        if result:
            phases.append(result)

    if not phases:
        print("::warning::Telemetry: No phase data could be extracted.")
        telemetry = build_telemetry([], resolved_models)
    else:
        telemetry = build_telemetry(phases, resolved_models)

    # Write telemetry artifact
    telemetry_path = Path("telemetry.json")
    telemetry_path.write_text(json.dumps(telemetry, indent=2) + "\n")
    print(f"Telemetry written to {telemetry_path}")

    # Write summary to GitHub Actions
    summary_path = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    write_summary(telemetry, summary_path)

    # Print summary to stdout for workflow log visibility
    print(f"\n{'='*60}")
    print("PIPELINE TELEMETRY SUMMARY")
    print(f"{'='*60}")
    for phase in phases:
        u = phase["usage"]
        print(
            f"  {phase['name']}: "
            f"input={format_tokens(u['inputTokens'])} "
            f"output={format_tokens(u['outputTokens'])} "
            f"cache_read={format_tokens(u['cacheReadTokens'])} "
            f"cache_write={format_tokens(u['cacheWriteTokens'])} "
            f"cost=${phase['estimated_cost_usd']:.4f} "
            f"duration={phase['duration_ms']/1000:.1f}s"
        )
    totals = telemetry["totals"]
    print(f"  {'—'*50}")
    print(
        f"  TOTAL: "
        f"input={format_tokens(totals['inputTokens'])} "
        f"output={format_tokens(totals['outputTokens'])} "
        f"cache_read={format_tokens(totals['cacheReadTokens'])} "
        f"cache_write={format_tokens(totals['cacheWriteTokens'])} "
        f"cost=${totals['estimated_cost_usd']:.4f} "
        f"duration={totals['duration_ms']/1000:.1f}s"
    )
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
