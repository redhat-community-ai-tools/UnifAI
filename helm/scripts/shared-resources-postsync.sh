#!/bin/bash
set -x
set +e
echo "Starting shared-resources postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
MONGO_PORT=$(wait_for_port mongodb) || exit 1
RMQ_PORT=$(wait_for_port rabbitmq) || exit 1
MONGO_IP=$(wait_for_service_name mongodb) || exit 1
RMQ_IP=$(wait_for_service_name rabbitmq) || exit 1  

# Create configmap
create_or_update_configmap shared-config \
  --from-literal=MONGODB_PORT="$MONGO_PORT" \
  --from-literal=RABBITMQ_PORT="$RMQ_PORT" \
  --from-literal=MONGODB_IP="$MONGO_IP" \
  --from-literal=RABBITMQ_IP="$RMQ_IP"