#!/bin/bash

set -x  # Print each command
set +e  # Disable immediate exit on error
echo "Starting identity-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"


# Create configmap
create_or_update_configmap identity-config \
  --from-literal=admin_allowed_users="$admin_allowed_users" \
  --from-literal=keycloak_base_url="$keycloak_base_url" \
  --from-literal=client_id="$client_id" \
  --from-literal=client_secret="$client_secret" \
  --from-literal=keycloak_realm="$keycloak_realm" \
  --from-literal=secret_key="$secret_key" \
  --from-literal=directory_provider="$directory_provider" \
  --from-literal=directory_url="$directory_url" \
  --from-literal=directory_verify_ssl="$directory_verify_ssl"