#!/bin/sh
# Log a message in extra initialization phase
# $1 - the log message
log() {
  echo "***** INIT: $1"
  echo "$(date) ***** INIT: $1" >>/tmp/init.log
}

set -e
log "Start user database initalization"
if [ ! -z "$MONGO_INITDB_ROOT_USERNAME" ] && [ ! -z "$MONGO_INITDB_ROOT_PASSWORD" ] && [ ! -z "$MONGO_INITDB_DATABASE" ] && [ ! -z "$USERDB_USER" ] && [ ! -z "$USERDB_PASSWORD" ]; then
  log "Creating database $MONGO_INITDB_DATABASE"
  $MONGOSHELL --eval "db.getSiblingDB(\"$MONGO_INITDB_DATABASE\").createUser({user: \"$USERDB_USER\", pwd: \"$USERDB_PASSWORD\", roles: [ \"readWrite\", \"dbAdmin\" ]})"
else
  log "Missing parameters to create database"
fi
log "Done with user database initialization"
