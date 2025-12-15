#!/bin/bash
set -x
set +e
echo "Starting multiagent postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
MULTIAGENT_ADDR=$(wait_for_ip unifai-multiagent-be) || exit 1
MULTIAGENT_PORT=$(wait_for_port unifai-multiagent-be) || exit 1
MULTIAGENT_IP=$(wait_for_service_name unifai-multiagent-be) || exit 1

# Create configmap
create_or_update_configmap multiagent-config \
  --from-literal=MULTIAGENT_ADDR="$MULTIAGENT_ADDR" \
  --from-literal=MULTIAGENT_PORT="$MULTIAGENT_PORT" \
  --from-literal=MULTIAGENT_IP="$MULTIAGENT_IP"