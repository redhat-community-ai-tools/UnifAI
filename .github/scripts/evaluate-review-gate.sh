#!/usr/bin/env bash
set -euo pipefail

CODE_REVIEW_THRESHOLD="${CODE_REVIEW_THRESHOLD:-8}"
CODE_REVIEW_FILE="${CODE_REVIEW_FILE:-code_review_output.txt}"
DESIGN_REVIEW_FILE="${DESIGN_REVIEW_FILE:-design_review_output.txt}"

CODE_SCORE=$(grep -oP 'Code Health Score:\s*\K[0-9]{1,2}(?=/10)' "$CODE_REVIEW_FILE" 2>/dev/null | tail -1 || true)
CODE_SCORE="${CODE_SCORE:-0}"

if ! [[ "$CODE_SCORE" =~ ^[0-9]+$ ]]; then
  CODE_SCORE=0
fi

if [ "$CODE_SCORE" = "0" ]; then
  echo "::warning::Code review score is 0. This may indicate a parse failure — check $CODE_REVIEW_FILE format."
fi

DESIGN_VERDICT=$(grep -oP '\*\*(?:APPROVE|NEEDS REVISION|REJECT)\*\*' "$DESIGN_REVIEW_FILE" 2>/dev/null | head -1 | tr -d '*' || true)

if [ -z "$DESIGN_VERDICT" ]; then
  DESIGN_VERDICT="UNKNOWN"
fi

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
