#!/bin/sh

set -e  # Exit on any error

echo ""
echo "------------------------------------------"
echo "🚀 Starting container with ROLE=\"$ROLE\""
echo "------------------------------------------"

case "$ROLE" in
  flask)
    echo "🟢 Starting Flask API (Server)..."
    . ~/venv/bin/activate
    exec gunicorn -w $GUNICORN_WORKERS --threads $GUNICORN_THREADS -b 0.0.0.0:$PORT --timeout $GUNICORN_TIMEOUT --access-logfile - --error-logfile - --chdir ~/app run.wsgi:application
    ;;
    
  # celery)
  #   echo "🔧 Starting Slack Celery worker with tasks concurrently : $CELERY_WORKER"
  #   . ~/venv/bin/activate
  #   exec celery -A celery_app.init worker -c $CELERY_WORKER --pool=solo --loglevel=info -Q $CELERY_QUEUES -n multiagent
  #   ;;

  debug)
    echo "🐞 Debug mode activated — container will stay alive."
    tail -f /dev/null
    ;;

  *)
    echo "❌ ERROR: Unknown ROLE \"$ROLE\""
    echo "Valid roles are: flask, celery, debug"
    exit 1
    ;;
esac
