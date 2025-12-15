#!/bin/bash

set -x  # Print each command
set +e  # Disable immediate exit on error
echo "Starting sso-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"


# Create configmap
create_or_update_configmap sso-config \
  --from-literal=admin_allowed_users="$admin_allowed_users" 
