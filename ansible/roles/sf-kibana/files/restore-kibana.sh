#!/bin/bash

DATE=$(date '+%Y-%m-%d')
KIBANA_HOST=${KIBANA_HOST:-"$(hostname -I | awk '{ print $1}' ):5601"}
BACKUP_DIR=${KIBANA_BACKUP_DIR:-'/usr/share/sf-config/kibana-backup'}
ALLOW_OVERWRITE=${KIBANA_ALLOW_OVERWRITE:-'true'}
RESTORE_FILE=${RESTORE_FILE:-''}

# Restore just one exported object
if [ -n "${RESTORE_FILE}" ] && [ -f "${RESTORE_FILE}" ]; then
    curl -X POST "${KIBANA_HOST}/api/saved_objects/_import?overwrite=$ALLOW_OVERWRITE" -H 'kbn-xsrf: true'  --form file=@"${RESTORE_FILE}"
else
    # POSSIBLE doc_types: config map canvas-workpad canvas-element index-pattern visualization search dashboard url
    for doc_type in visualization dashboard; do
        if [ -f "${BACKUP_DIR}/${doc_type}.ndjson" ]; then
            curl -X POST "${KIBANA_HOST}/api/saved_objects/_import?overwrite=$ALLOW_OVERWRITE" -H 'kbn-xsrf: true'  --form file=@"${BACKUP_DIR}/${doc_type}.ndjson"
            # Change the backup name to other, to avoid once restore
            mv "${BACKUP_DIR}/${doc_type}.ndjson" "${BACKUP_DIR}/${doc_type}-${DATE}.ndjson"
        fi
    done
fi
