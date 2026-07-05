"""Shared scoring logic for CI pipeline scripts."""


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
