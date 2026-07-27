#!/bin/sh

set -e

echo ""
echo "------------------------------------------"
echo "Starting container with ROLE=\"$ROLE\""
echo "------------------------------------------"

case "$ROLE" in
  flask)
    echo "Starting Flask API (Server)..."
    . ~/backend/venv/bin/activate
    exec gunicorn -w $GUNICORN_WORKERS --threads $GUNICORN_THREADS -b 0.0.0.0:$PORT --timeout $GUNICORN_TIMEOUT --access-logfile - --error-logfile - run.wsgi:application
    ;;

  slack-socket)
    echo "Starting Slack Socket Mode handler..."
    . ~/backend/venv/bin/activate
    exec python -m slack_commands.socket_handler
    ;;

  debug)
    echo "Debug mode activated - container will stay alive."
    tail -f /dev/null
    ;;

  *)
    echo "ERROR: Unknown ROLE \"$ROLE\""
    echo "Valid roles are: flask, slack-socket, debug"
    exit 1
    ;;
esac
