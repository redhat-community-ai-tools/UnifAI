#!/bin/bash
# ==============================================================================
# postsync-lib.sh - Shared utilities for ArgoCD postsync hooks
# 
# Usage: source this file in your postsync hook scripts
# ==============================================================================

set -uo pipefail

# Configuration (override before sourcing if needed)
: "${WAIT_MAX_RETRIES:=60}"
: "${WAIT_INTERVAL_SECONDS:=10}"

# ==============================================================================
# Logging
# ==============================================================================
_log() {
  local level=$1; shift
  echo "[$level] $(date '+%H:%M:%S') $*"
}

log_info()  { _log "INFO" "$@"; }
log_warn()  { _log "WARN" "$@"; }
log_error() { _log "ERROR" "$@" >&2; }

# ==============================================================================
# Service Discovery
# ==============================================================================

# Generic wait function - waits for a kubectl jsonpath to return a value
# Usage: wait_for_field <service> <jsonpath> [description]
# Returns: 0 on success (prints value), 1 on timeout
wait_for_field() {
  local svc=$1
  local jsonpath=$2
  local description=${3:-"$jsonpath"}
  local value=""
  
  for ((attempt=1; attempt<=WAIT_MAX_RETRIES; attempt++)); do
    value=$(kubectl get svc "$svc" -o jsonpath="$jsonpath" 2>/dev/null)
    if [[ -n "$value" ]]; then
      echo "$value"
      return 0
    fi
    log_info "Waiting for $svc $description... ($attempt/$WAIT_MAX_RETRIES)"
    sleep "$WAIT_INTERVAL_SECONDS"
  done
  
  log_error "Timed out waiting for $svc $description"
  return 1
}

# Convenience wrappers (return 1 on failure instead of exit)
wait_for_ip() {
  wait_for_field "$1" '{.spec.clusterIP}' "ClusterIP"
}

wait_for_port() {
  wait_for_field "$1" '{.spec.ports[0].port}' "port"
}

wait_for_service_name() {
  wait_for_field "$1" '{.metadata.name}' "name"
}

# ==============================================================================
# ConfigMap Management
# ==============================================================================

# Creates or updates a ConfigMap idempotently
# Usage: create_or_update_configmap <name> --from-literal=KEY=value ...
create_or_update_configmap() {
  local cm_name=$1; shift
  
  kubectl create configmap "$cm_name" "$@" \
    --dry-run=client -o yaml | kubectl apply -f -
  
  log_info "ConfigMap '$cm_name' applied successfully"
}