#!/usr/bin/env bash
set -euo pipefail

CODE_REVIEW_THRESHOLD="${CODE_REVIEW_THRESHOLD:-8}"
CODE_REVIEW_FILE="${CODE_REVIEW_FILE:-code_review_output.txt}"
ARCH_REVIEW_FILE="${ARCH_REVIEW_FILE:-arch_review_output.txt}"

strip_ansi() { sed 's/\x1b\[[0-9;]*m//g' "$1"; }

# --- Parse code review score with explicit failure tracking ---
CODE_SCORE=""
CODE_PARSE_STATUS="ok"

if [ ! -f "$CODE_REVIEW_FILE" ]; then
  CODE_PARSE_STATUS="file_missing"
elif [ ! -s "$CODE_REVIEW_FILE" ]; then
  CODE_PARSE_STATUS="file_empty"
else
  CODE_SCORE=$(strip_ansi "$CODE_REVIEW_FILE" | grep -oP 'Code Health Score:\s*\K[0-9]{1,2}(?=/10)' | tail -1 || true)
  if [ -z "$CODE_SCORE" ]; then
    CODE_PARSE_STATUS="pattern_not_found"
  elif ! [[ "$CODE_SCORE" =~ ^[0-9]+$ ]]; then
    CODE_PARSE_STATUS="invalid_value"
    CODE_SCORE=""
  fi
fi

if [ "$CODE_PARSE_STATUS" != "ok" ]; then
  echo "::warning::Could not extract code review score (reason: $CODE_PARSE_STATUS). Check $CODE_REVIEW_FILE."
  CODE_SCORE=0
fi

# --- Parse architecture review verdict with explicit failure tracking ---
ARCH_VERDICT=""
ARCH_PARSE_STATUS="ok"

if [ ! -f "$ARCH_REVIEW_FILE" ]; then
  ARCH_PARSE_STATUS="file_missing"
elif [ ! -s "$ARCH_REVIEW_FILE" ]; then
  ARCH_PARSE_STATUS="file_empty"
else
  ARCH_VERDICT=$(strip_ansi "$ARCH_REVIEW_FILE" | grep -oP '\*\*(?:APPROVE|NEEDS REVISION|REJECT)\*\*' | head -1 | tr -d '*' || true)
  if [ -z "$ARCH_VERDICT" ]; then
    ARCH_PARSE_STATUS="pattern_not_found"
  fi
fi

if [ "$ARCH_PARSE_STATUS" != "ok" ]; then
  echo "::warning::Could not extract architecture verdict (reason: $ARCH_PARSE_STATUS). Check $ARCH_REVIEW_FILE."
  ARCH_VERDICT="UNKNOWN"
fi

# --- Publish gate results to job summary ---
{
  echo ""
  echo "---"
  echo ""
  echo "## Review Gate Results"
  echo ""
  echo "| Review | Result | Threshold | Status |"
  echo "|--------|--------|-----------|--------|"
} >> "$GITHUB_STEP_SUMMARY"

if [ "$ARCH_VERDICT" = "APPROVE" ]; then
  ARCH_STATUS="✅ PASS"
  ARCH_PASS=true
else
  ARCH_STATUS="❌ FAIL ($ARCH_VERDICT)"
  ARCH_PASS=false
fi
echo "| Architecture Review | $ARCH_VERDICT | APPROVE | $ARCH_STATUS |" >> "$GITHUB_STEP_SUMMARY"

if [ "$CODE_SCORE" -ge "$CODE_REVIEW_THRESHOLD" ]; then
  CODE_STATUS="✅ PASS"
  CODE_PASS=true
else
  CODE_STATUS="❌ FAIL"
  CODE_PASS=false
fi
echo "| Code Review | $CODE_SCORE/10 | ≥${CODE_REVIEW_THRESHOLD}/10 | $CODE_STATUS |" >> "$GITHUB_STEP_SUMMARY"

echo "" >> "$GITHUB_STEP_SUMMARY"

if [ "$ARCH_PASS" = "false" ] || [ "$CODE_PASS" = "false" ]; then
  echo "::error::Review gate failed. Architecture: $ARCH_VERDICT, Code: $CODE_SCORE/10 (threshold: $CODE_REVIEW_THRESHOLD)"
  exit 1
fi

echo "✅ **All review gates passed.**" >> "$GITHUB_STEP_SUMMARY"
