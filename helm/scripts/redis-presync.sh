#!/bin/bash

set +e  # Disable immediate exit on error
echo "Starting redis-presync hook..."
# Source common functions
source "$(dirname "$0")/postsync-lib.sh"


# Create configmap
# create_or_update_configmap redis-config \
#   --from-literal=REDIS_PORT="$redis_port" \
#   --from-literal=REDIS_USERNAME="$redis_username" \
#   --from-literal=REDIS_PASSWORD="$redis_password" \
#   --from-literal=RI_APP_PORT="$redis_insight_port" \
#   --from-literal=RI_REDIS_PORT="$redis_port" \
#   --from-literal=RI_REDIS_USERNAME="$redis_username" \
#   --from-literal=RI_REDIS_PASSWORD="$redis_password"

#create configmap
create_or_update_resource configmap redis-config \
  --from-literal=REDIS_PORT="$redis_port" \
  --from-literal=RI_APP_PORT="$redis_insight_port" \
  --from-literal=RI_REDIS_PORT="$redis_port" 

#create secret
create_or_update_resource "secret generic" redis-secret \
  --from-literal=REDIS_USERNAME="$redis_username" \
  --from-literal=REDIS_PASSWORD="$redis_password" \
  --from-literal=RI_REDIS_USERNAME="$redis_username" \
  --from-literal=RI_REDIS_PASSWORD="$redis_password"