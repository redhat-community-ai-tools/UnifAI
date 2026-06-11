#!/bin/bash
set +e
echo "Starting backend postsync hook..."

source "$(dirname "$0")/postsync-lib.sh"

BACKEND_ADDR=$(wait_for_ip unifai-backend) || exit 1
BACKEND_PORT=$(wait_for_port unifai-backend) || exit 1
BACKEND_IP=$(wait_for_service_name unifai-backend) || exit 1

create_or_update_configmap backend-config \
  --from-literal=BACKEND_ADDR="$BACKEND_ADDR" \
  --from-literal=BACKEND_PORT="$BACKEND_PORT" \
  --from-literal=BACKEND_IP="$BACKEND_IP"
