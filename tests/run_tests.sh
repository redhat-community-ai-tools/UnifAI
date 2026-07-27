#!/bin/bash

SUITE="${1:-all}"
shift 2>/dev/null || true
EXTRA_ARGS="$@"

LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_ARGS="--log-cli-level=${LOG_LEVEL}"

REPORTS_DIR="${REPORTS_DIR:-}"
REPORT_ARGS=""
if [ -n "$REPORTS_DIR" ] && [ -d "$REPORTS_DIR" ]; then
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  REPORT_ARGS="--html=${REPORTS_DIR}/report_${SUITE}_${TIMESTAMP}.html --self-contained-html --junitxml=${REPORTS_DIR}/junit_${SUITE}_${TIMESTAMP}.xml"
fi

SERVE_REPORTS="${SERVE_REPORTS:-false}"
SERVE_PORT="${SERVE_PORT:-8080}"

echo ""
echo "============================================"
echo "  UnifAI Test Runner"
echo "============================================"
echo "  Suite         : $SUITE"
echo "  Log level     : $LOG_LEVEL"
echo "  Extra args    : ${EXTRA_ARGS:-<none>}"
echo "  Reports dir   : ${REPORTS_DIR:-<disabled>}"
echo "  Serve reports : $SERVE_REPORTS"
echo "============================================"
echo ""

HOME_DIR="$HOME"
TEST_EXIT=0

# --------------------------------------------------------------------------
# Start report server in background (if enabled)
# --------------------------------------------------------------------------
if [ "$SERVE_REPORTS" = "true" ] && [ -n "$REPORTS_DIR" ] && [ -d "$REPORTS_DIR" ]; then
  echo "Starting report server on port $SERVE_PORT (background)..."
  cd "$REPORTS_DIR"
  python3 -m http.server "$SERVE_PORT" &
  SERVE_PID=$!
  echo "Report server PID: $SERVE_PID"
  cd "$HOME_DIR"
fi

# --------------------------------------------------------------------------
# Test suites
# --------------------------------------------------------------------------
case "$SUITE" in

  debug)
    echo ">>> Debug mode activated — container will stay alive."
    echo ""
    echo "Environment variables:"
    env | sort
    echo ""
    echo "Python version : $(python3 --version)"
    echo "Pytest version : $(pytest --version 2>&1 | head -1)"
    echo ""
    echo "Available test paths:"
    [ -d "$HOME_DIR/rag/tests" ]         && echo "  - rag/tests/"
    [ -d "$HOME_DIR/multi-agent/tests" ] && echo "  - multi-agent/tests/"
    echo ""
    tail -f /dev/null
    ;;

  rag)
    echo ">>> Running RAG tests..."
    cd "$HOME_DIR/rag"
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  rag-unit)
    echo ">>> Running RAG unit tests..."
    cd "$HOME_DIR/rag"
    pytest tests/unit/ -v -s --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  rag-e2e)
    echo ">>> Running RAG e2e tests..."
    cd "$HOME_DIR/rag"
    pytest tests/e2e/ -v -s --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  rag-smoke)
    echo ">>> Running RAG smoke tests..."
    cd "$HOME_DIR/rag"
    pytest tests/smoke/ -v -s --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  multi-agent)
    echo ">>> Running Multi-Agent tests..."
    cd "$HOME_DIR/multi-agent"
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  multi-agent-e2e)
    echo ">>> Running Multi-Agent e2e tests..."
    cd "$HOME_DIR/multi-agent"
    pytest tests/e2e/ -v -s --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  multi-agent-unit)
    echo ">>> Running Multi-Agent unit tests..."
    cd "$HOME_DIR/multi-agent"
    pytest tests/unit/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  multi-agent-integration)
    echo ">>> Running Multi-Agent integration tests..."
    cd "$HOME_DIR/multi-agent"
    pytest tests/integration/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  identity)
    echo ">>> Running Identity tests..."
    cd "$HOME_DIR/shared-resources/identity"
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  identity-smoke)
    echo ">>> Running Identity smoke tests..."
    cd "$HOME_DIR/shared-resources/identity"
    pytest tests/smoke/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  identity-unit)
    echo ">>> Running Identity unit tests..."
    cd "$HOME_DIR/shared-resources/identity"
    pytest tests/unit/ -v --tb=short --color=yes $LOG_ARGS $REPORT_ARGS $EXTRA_ARGS || TEST_EXIT=$?
    ;;

  all)
    echo ">>> Running ALL tests..."
    echo ""

    echo "--- RAG tests ---"
    cd "$HOME_DIR/rag"
    RAG_REPORT_ARGS=""
    if [ -n "$REPORTS_DIR" ] && [ -d "$REPORTS_DIR" ]; then
      RAG_REPORT_ARGS="--html=${REPORTS_DIR}/report_rag_${TIMESTAMP}.html --self-contained-html --junitxml=${REPORTS_DIR}/junit_rag_${TIMESTAMP}.xml"
    fi
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $RAG_REPORT_ARGS $EXTRA_ARGS || RAG_EXIT=$?
    echo ""

    echo "--- Multi-Agent tests ---"
    cd "$HOME_DIR/multi-agent"
    MA_REPORT_ARGS=""
    if [ -n "$REPORTS_DIR" ] && [ -d "$REPORTS_DIR" ]; then
      MA_REPORT_ARGS="--html=${REPORTS_DIR}/report_multi-agent_${TIMESTAMP}.html --self-contained-html --junitxml=${REPORTS_DIR}/junit_multi-agent_${TIMESTAMP}.xml"
    fi
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $MA_REPORT_ARGS $EXTRA_ARGS || MA_EXIT=$?
    echo ""

    echo "--- Identity tests ---"
    cd "$HOME_DIR/shared-resources/identity"
    IDENTITY_REPORT_ARGS=""
    if [ -n "$REPORTS_DIR" ] && [ -d "$REPORTS_DIR" ]; then
      IDENTITY_REPORT_ARGS="--html=${REPORTS_DIR}/report_identity_${TIMESTAMP}.html --self-contained-html --junitxml=${REPORTS_DIR}/junit_identity_${TIMESTAMP}.xml"
    fi
    pytest tests/ -v --tb=short --color=yes $LOG_ARGS $IDENTITY_REPORT_ARGS $EXTRA_ARGS || IDENTITY_EXIT=$?
    echo ""

    echo "============================================"
    echo "  Results"
    echo "============================================"
    echo "  RAG          : ${RAG_EXIT:-0} (0=pass)"
    echo "  Multi-Agent  : ${MA_EXIT:-0} (0=pass)"
    echo "============================================"

    if [ "${RAG_EXIT:-0}" -ne 0 ] || [ "${MA_EXIT:-0}" -ne 0 ]; then
      TEST_EXIT=1
    fi
    ;;

  *)
    echo "ERROR: Unknown suite '$SUITE'"
    echo ""
    echo "Usage: $0 <suite> [pytest-args...]"
    echo ""
    echo "Available suites:"
    echo "  debug                - Log env and sleep infinity (for exec-in debugging)"
    echo "  all                  - Run everything"
    echo "  rag                  - All RAG tests"
    echo "  rag-unit             - RAG unit tests only"
    echo "  rag-smoke            - RAG smoke tests only"
    echo "  rag-e2e              - RAG e2e tests only"
    echo "  multi-agent          - All multi-agent tests"
    echo "  multi-agent-e2e      - Multi-agent e2e tests only"
    echo "  multi-agent-unit     - Multi-agent unit tests only"
    echo "  multi-agent-integration - Multi-agent integration tests only"
    echo ""
    echo "Examples:"
    echo "  $0 rag-e2e --num-docs 10 --concurrent-uploads 5"
    echo "  $0 multi-agent -m unit"
    echo "  $0 all --junitxml=/tmp/results.xml"
    exit 1
    ;;
esac

echo ""
echo "Tests exited with code: $TEST_EXIT"

# Keep the container alive so the Deployment doesn't restart and re-run tests.
# The report server (if enabled) is already running in the background.
echo "Container staying alive. To re-run tests, delete this pod."
tail -f /dev/null
