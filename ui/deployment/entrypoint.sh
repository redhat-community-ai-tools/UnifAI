#!/bin/sh
set -e

# Default VERSION if not provided
: "${VERSION:=N/A}"

# Write runtime config.json
cat <<EOF > /usr/share/nginx/html/config.json
{
  "version": "${VERSION}"
}
EOF

# Replace env vars inside nginx.conf
export DOLLAR='$'
envsubst < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Start nginx
exec nginx -g 'daemon off;'
