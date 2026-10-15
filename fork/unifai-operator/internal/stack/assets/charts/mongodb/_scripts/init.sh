#!/bin/sh
echo "Start initialization"
echo "Copy init scripts"
# Copy optional initialization scripts only to first cluster instance (initial primary on a new replicaset)
if [ "$HOSTNAME" = "{{ include "mongodb.fullname" . }}-0" ]; then
    cp /scripts/0*-init-*.sh /initscripts
    if [ -d /extrascripts ]; then
    echo "Copy extra scripts"
    cp /extrascripts/* /initscripts
    fi
    if [ -d /customscripts ]; then
    echo "Copy custom scripts"
    cp /customscripts/* /initscripts
    fi
fi
# Copy extra initialization scripts for ReplicaSet cluster
cp /scripts/extra-*.sh /extrainitscripts
echo "Copy custom configuration"
touch /configs/custom.conf
if [ -d /customconfig ]; then
    echo "Create custom mongodb config"
    cat /customconfig/* >>/configs/custom.conf
fi
if [ -d /extraconfigs ]; then
    echo "Add extra configs to custom mongodb config"
    cat /extraconfigs/* >>/configs/custom.conf
fi
{{- if .Values.replicaSet.enabled }}
echo "Copy replicaset key"
if [ -f /keyfile-secret/keyfile ]; then
    echo "Using keyfile from secret"
    cp /keyfile-secret/keyfile /replicaset/keyfile
else
    echo "Using configured key"
    echo "{{ .Values.replicaSet.key }}" > /replicaset/keyfile
fi
chmod 400 /replicaset/keyfile
{{- end }}    
echo "Initialization done."