#!/bin/bash
set -x
set +e
echo "Starting dataflow postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
DATAFLOW_ADDR=$(wait_for_ip unifai-dataflow-server) || exit 1
DATAFLOW_PORT=$(wait_for_port unifai-dataflow-server) || exit 1
DATAFLOW_IP=$(wait_for_service_name unifai-dataflow-server) || exit 1 

# Create configmap
create_or_update_configmap unifai-dataflow-config \
  --from-literal=DATAFLOW_ADDR="$DATAFLOW_ADDR" \
  --from-literal=DATAFLOW_PORT="$DATAFLOW_PORT" \
  --from-literal=DATAFLOW_IP="$DATAFLOW_IP"