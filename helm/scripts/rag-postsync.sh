#!/bin/bash
set +e
echo "Starting rag postsync hook..."

# Source common functions
source "$(dirname "$0")/postsync-lib.sh"

# Get service details
RAG_ADDR=$(wait_for_ip unifai-rag-server) || exit 1
RAG_PORT=$(wait_for_port unifai-rag-server) || exit 1
RAG_IP=$(wait_for_service_name unifai-rag-server) || exit 1 

# Create configmap
create_or_update_configmap unifai-rag-config \
  --from-literal=RAG_ADDR="$RAG_ADDR" \
  --from-literal=RAG_PORT="$RAG_PORT" \
  --from-literal=RAG_IP="$RAG_IP"