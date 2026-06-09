#!/usr/bin/env bash
set -euo pipefail

CODE_REVIEW_THRESHOLD="${CODE_REVIEW_THRESHOLD:-8}"
CODE_REVIEW_FILE="${CODE_REVIEW_FILE:-code_review_output.txt}"
DESIGN_REVIEW_FILE="${DESIGN_REVIEW_FILE:-design_review_output.txt}"

# --- Parse code review score with explicit failure tracking ---
CODE_SCORE=""
CODE_PARSE_STATUS="ok"

if [ ! -f "$CODE_REVIEW_FILE" ]; then
  CODE_PARSE_STATUS="file_missing"
elif [ ! -s "$CODE_REVIEW_FILE" ]; then
  CODE_PARSE_STATUS="file_empty"
else
  CODE_SCORE=$(grep -oP 'Code Health Score:\s*\K[0-9]{1,2}(?=/10)' "$CODE_REVIEW_FILE" | tail -1 || true)
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

# --- Parse design review verdict with explicit failure tracking ---
DESIGN_VERDICT=""
DESIGN_PARSE_STATUS="ok"

if [ ! -f "$DESIGN_REVIEW_FILE" ]; then
  DESIGN_PARSE_STATUS="file_missing"
elif [ ! -s "$DESIGN_REVIEW_FILE" ]; then
  DESIGN_PARSE_STATUS="file_empty"
else
  DESIGN_VERDICT=$(grep -oP '\*\*(?:APPROVE|NEEDS REVISION|REJECT)\*\*' "$DESIGN_REVIEW_FILE" | head -1 | tr -d '*' || true)
  if [ -z "$DESIGN_VERDICT" ]; then
    DESIGN_PARSE_STATUS="pattern_not_found"
  fi
fi

if [ "$DESIGN_PARSE_STATUS" != "ok" ]; then
  echo "::warning::Could not extract design verdict (reason: $DESIGN_PARSE_STATUS). Check $DESIGN_REVIEW_FILE."
  DESIGN_VERDICT="UNKNOWN"
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

if [ "$DESIGN_VERDICT" = "APPROVE" ]; then
  DESIGN_STATUS="✅ PASS"
  DESIGN_PASS=true
else
  DESIGN_STATUS="❌ FAIL ($DESIGN_VERDICT)"
  DESIGN_PASS=false
fi
echo "| Design Review | $DESIGN_VERDICT | APPROVE | $DESIGN_STATUS |" >> "$GITHUB_STEP_SUMMARY"

if [ "$CODE_SCORE" -ge "$CODE_REVIEW_THRESHOLD" ]; then
  CODE_STATUS="✅ PASS"
  CODE_PASS=true
else
  CODE_STATUS="❌ FAIL"
  CODE_PASS=false
fi
echo "| Code Review | $CODE_SCORE/10 | ≥${CODE_REVIEW_THRESHOLD}/10 | $CODE_STATUS |" >> "$GITHUB_STEP_SUMMARY"

echo "" >> "$GITHUB_STEP_SUMMARY"

if [ "$DESIGN_PASS" = "false" ] || [ "$CODE_PASS" = "false" ]; then
  echo "::error::Review gate failed. Design: $DESIGN_VERDICT, Code: $CODE_SCORE/10 (threshold: $CODE_REVIEW_THRESHOLD)"
  exit 1
fi

echo "✅ **All review gates passed.**" >> "$GITHUB_STEP_SUMMARY"
