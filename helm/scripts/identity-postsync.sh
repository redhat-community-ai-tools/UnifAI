#!/bin/bash
set +e
echo "Starting identity postsync hook..."

source "$(dirname "$0")/postsync-lib.sh"

IDENTITY_ADDR=$(wait_for_ip identity) || exit 1
IDENTITY_PORT=$(wait_for_port identity) || exit 1
IDENTITY_IP=$(wait_for_service_name identity) || exit 1

create_or_update_configmap identity-svc-config \
  --from-literal=IDENTITY_SVC_ADDR="$IDENTITY_ADDR" \
  --from-literal=IDENTITY_SVC_PORT="$IDENTITY_PORT" \
  --from-literal=IDENTITY_SVC_IP="$IDENTITY_IP" || exit 1
