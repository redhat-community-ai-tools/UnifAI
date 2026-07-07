"""Shared scoring logic for CI pipeline scripts."""


def to_int(value, default: int = 0, *, min_value: int = 0) -> int:
    """Coerce ints, numeric strings, and floats; clamp below *min_value*; return *default* on failure."""
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        try:
            number = int(float(value))
        except (TypeError, ValueError, OverflowError):
            return default
    return max(min_value, number)


def require_int(value, *, default_if_empty: int, min_value: int = 0) -> int | None:
    """Coerce to int for strict JSON parsing.

    Returns *default_if_empty* for null/empty input, the coerced int on success,
    or None when the value is present but invalid or below *min_value*.
    """
    if value is None or value == "":
        return default_if_empty
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        try:
            number = int(float(value))
        except (TypeError, ValueError, OverflowError):
            return None
    if number < min_value:
        return None
    return number


def _non_negative_count(value, default: int = 0) -> int:
    return to_int(value, default=default, min_value=0)


def compute_deterministic_score(code_findings: dict, files_changed: int) -> int:
    """Compute score using the Severity Floor hybrid formula.

    MAJOR/CRITICAL penalties are flat (never diluted by scope).
    MINOR penalties are density-based (diluted by file count, normalized to 5-file baseline).
    """
    critical = _non_negative_count(code_findings.get("critical", 0))
    major = _non_negative_count(code_findings.get("major", 0))
    minor = _non_negative_count(code_findings.get("minor", 0))
    files_changed = to_int(files_changed, default=1, min_value=0) or 1

    critical_penalty = critical * 3.0
    major_penalty = major * 1.5
    minor_penalty = (minor * 0.5) / max(1, files_changed / 5)

    score = 10 - critical_penalty - major_penalty - minor_penalty
    return max(1, min(10, round(score)))
