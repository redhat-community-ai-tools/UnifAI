#!/bin/bash
set +e
echo "Starting shared-resources postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
MONGO_PORT=$(wait_for_port mongodb) || exit 1
RMQ_PORT=$(wait_for_port rabbitmq) || exit 1
REDIS_PORT=$(wait_for_port redis) || exit 1
TEMPORAL_PORT=$(wait_for_port temporal) || exit 1
MONGO_IP=$(wait_for_service_name mongodb) || exit 1
RMQ_IP=$(wait_for_service_name rabbitmq) || exit 1  
REDIS_IP=$(wait_for_service_name redis) || exit 1
TEMPORAL_IP=$(wait_for_service_name temporal) || exit 1

UMAMI_URL=$umami_url
UMAMI_WEBSITE_NAME=$umami_website_name
UMAMI_USERNAME=$umami_username
UMAMI_PASSWORD=$umami_password
REDIS_PASSWORD=$redis_password
# Create configmap
# create_or_update_configmap shared-config \
#   --from-literal=MONGODB_PORT="$MONGO_PORT" \
#   --from-literal=RABBITMQ_PORT="$RMQ_PORT" \
#   --from-literal=REDIS_PORT="$REDIS_PORT" \
#   --from-literal=TEMPORAL_PORT="$TEMPORAL_PORT" \
#   --from-literal=MONGODB_IP="$MONGO_IP" \
#   --from-literal=RABBITMQ_IP="$RMQ_IP" \
#   --from-literal=REDIS_IP="$REDIS_IP" \
#   --from-literal=TEMPORAL_IP="$TEMPORAL_IP" \
#   --from-literal=UMAMI_URL="$UMAMI_URL" \
#   --from-literal=UMAMI_WEBSITE_NAME="$UMAMI_WEBSITE_NAME" \
#   --from-literal=UMAMI_USERNAME="$UMAMI_USERNAME" \
#   --from-literal=UMAMI_PASSWORD="$UMAMI_PASSWORD" \
#   --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD"

create_or_update_resource configmap shared-config \
  --from-literal=MONGODB_PORT="$MONGO_PORT" \
  --from-literal=RABBITMQ_PORT="$RMQ_PORT" \
  --from-literal=REDIS_PORT="$REDIS_PORT" \
  --from-literal=TEMPORAL_PORT="$TEMPORAL_PORT" \
  --from-literal=MONGODB_IP="$MONGO_IP" \
  --from-literal=RABBITMQ_IP="$RMQ_IP" \
  --from-literal=REDIS_IP="$REDIS_IP" \
  --from-literal=TEMPORAL_IP="$TEMPORAL_IP" \
  --from-literal=UMAMI_URL="$UMAMI_URL" \
  --from-literal=UMAMI_WEBSITE_NAME="$UMAMI_WEBSITE_NAME" \
  --from-literal=admin_allowed_users="$admin_allowed_users"

create_or_update_resource "secret generic" shared-secret \
  --from-literal=UMAMI_USERNAME="$UMAMI_USERNAME" \
  --from-literal=UMAMI_PASSWORD="$UMAMI_PASSWORD" \
  --from-literal=REDIS_PASSWORD="$REDIS_PASSWORD" \
  --from-literal=SECRET_KEY="$secret_key" \
  --from-literal=VAULT_ROLE_ID="$vault_role_id" \
  --from-literal=VAULT_SECRET_ID="$vault_secret_id" \
  --from-literal=LANGFUSE_BASE_URL="$langfuse_base_url" \
  --from-literal=LANGFUSE_PUBLIC_KEY="$langfuse_public_key" \
  --from-literal=LANGFUSE_SECRET_KEY="$langfuse_secret_key" \
  --from-literal=slack_signing_secret="$slack_signing_secret" \
  --from-literal=SLACK_APP_TOKEN="$slack_app_token" \
  --from-literal=SLACK_BOT_TOKEN="$slack_bot_token"