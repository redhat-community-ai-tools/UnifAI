#!/bin/bash

set +e  # Disable immediate exit on error
echo "Starting multiagent-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

#create secret
create_or_update_resource "secret generic" multiagent-be-secret \
  --from-literal=CREDENTIAL_ENCRYPTION_KEY="$CREDENTIAL_ENCRYPTION_KEY" \
  --from-literal=MCP_AUTH_STATE_SECRET="$MCP_AUTH_STATE_SECRET" \
  --from-literal=gemini_api_key="$gemini_api_key" \
  --from-literal=gemini_model_name="$gemini_model_name"

# GCP service account key for Vertex AI (stored base64-encoded in Vault)
if [ -n "$GCP_SA_KEY_JSON_B64" ]; then
  echo "$GCP_SA_KEY_JSON_B64" | base64 -d > /tmp/gcp-sa-key.json
  create_or_update_resource "secret generic" gcp-vertex-credentials \
    --from-file=gcp-sa-key.json=/tmp/gcp-sa-key.json
  rm -f /tmp/gcp-sa-key.json
  log_info "GCP Vertex AI credentials secret created"
else
  log_warn "gcp_sa_key_json_b64 not set, skipping GCP Vertex credentials"
fi
