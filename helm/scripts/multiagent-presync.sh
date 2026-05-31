#!/bin/bash

set +e  # Disable immediate exit on error
echo "Starting multiagent-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

#create secret
create_or_update_resource "secret generic" multiagent-be-secret \
  --from-literal=CREDENTIAL_ENCRYPTION_KEY="$CREDENTIAL_ENCRYPTION_KEY" \
  --from-literal=MCP_AUTH_STATE_SECRET="$MCP_AUTH_STATE_SECRET"