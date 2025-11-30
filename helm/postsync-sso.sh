#!/bin/bash

set -x  # Print each command
set +e  # Disable immediate exit on error
echo "Starting postsync hook..."

kubectl delete configmap sso-config
kubectl create configmap sso-config \
  --from-literal=admin_allowed_users="$admin_allowed_users" \
  --dry-run=client -o yaml | kubectl apply -f -