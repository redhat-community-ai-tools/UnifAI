#!/bin/bash

set +e  # Disable immediate exit on error
echo "Starting logging-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

#create secret
create_or_update_resource "secret generic" logging-secret \
  --from-literal=OTEL_AUTH_TOKEN="$otel_auth_token" \
  --from-literal=OTEL_ENDPOINT="$otel_endpoint" \
  --from-literal=SUMOLOGIC_ENDPOINT="$sumologic_endpoint"