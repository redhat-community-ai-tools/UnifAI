#!/bin/sh

set -e  # Exit on any error

echo ""
echo "------------------------------------------"
echo "🚀 Starting container with ROLE=\"$ROLE\""
echo "------------------------------------------"

case "$ROLE" in
  flask)
    echo "🟢 Starting Flask API (Gunicorn)..."
    exec venv/bin/gunicorn -b 0.0.0.0:$PORT --capture-output --log-level ${LOG_LEVEL:-info} --access-logfile - --error-logfile - bootstrap.flask_app:app
    ;;

  dev)
    echo "🐞 Development mode activated — container will stay alive."
    exec venv/bin/python3.11 -m bootstrap.flask_app
    ;;

  debug)
    echo "🐞 Debug mode activated — container will stay alive."
    tail -f /dev/null
    ;;

  *)
    echo "❌ ERROR: Unknown ROLE \"$ROLE\""
    echo "Valid roles are: flask, dev, debug"
    exit 1
    ;;
esac
