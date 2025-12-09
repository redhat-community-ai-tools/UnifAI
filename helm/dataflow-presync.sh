#!/bin/bash

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_info "Starting presync hook for dataflow"

# Validate that required environment variables are set
MISSING_VARS=()

if [[ -z "${default_slack_bot_token}" ]]; then
    MISSING_VARS+=("default_slack_bot_token")
fi

if [[ -z "${default_slack_user_token}" ]]; then
    MISSING_VARS+=("default_slack_user_token")
fi

# Warning if variables are missing (but continue with empty values for optional secrets)
if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    log_warn "The following environment variables are not set:"
    for var in "${MISSING_VARS[@]}"; do
        log_warn "  - $var"
    done
    log_warn "Secret will be created with empty values for these variables."
    log_warn "Make sure to set these variables if Slack integration is required."
fi

# Create Secret with Slack tokens from environment variables
log_info "Creating/updating Secret 'unifai-dataflow-secrets'..."

SECRET_NAME="unifai-dataflow-secrets"

# Check if secret already exists
if kubectl get secret "$SECRET_NAME" &>/dev/null; then
    log_info "Secret '$SECRET_NAME' already exists. Updating..."
else
    log_info "Secret '$SECRET_NAME' does not exist. Creating..."
fi

# Create or update the secret
kubectl create secret generic "$SECRET_NAME" \
    --from-literal=default_slack_bot_token="${default_slack_bot_token:-}" \
    --from-literal=default_slack_user_token="${default_slack_user_token:-}" \
    --dry-run=client -o yaml | kubectl apply -f -

if [[ $? -eq 0 ]]; then
    log_info "Secret '$SECRET_NAME' created/updated successfully"
else
    log_error "Failed to create/update Secret '$SECRET_NAME'"
    exit 1
fi

# Verify the secret was created
if kubectl get secret "$SECRET_NAME" &>/dev/null; then
    log_info "Verified: Secret '$SECRET_NAME' exists"
    
    # Show secret keys (not values) for verification
    log_info "Secret contains the following keys:"
    kubectl get secret "$SECRET_NAME" -o jsonpath='{.data}' | jq -r 'keys[]' 2>/dev/null || true
else
    log_error "Verification failed: Secret '$SECRET_NAME' not found"
    exit 1
fi

log_info "Presync hook completed successfully"

