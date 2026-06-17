#!/bin/sh
set -e

ln -sf /dev/stdout /tmp/nginx_access.log
ln -sf /dev/stderr /tmp/nginx_error.log

export DOLLAR='$'
envsubst '$APP_SERVICE_NAME $APP_SERVICE_PORT $API_ENDPOINT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

exec nginx -g 'daemon off;'
