#!/bin/bash

KIBANA_HOST=${KIBANA_HOST:-"$(hostname -I | awk '{print $1}'):5601"}
BACKUP_DIR=${KIBANA_BACKUP_DIR:-'/usr/share/sf-config/kibana-backup'}

if [ ! -d "${BACKUP_DIR}" ]; then
    mkdir -p "${BACKUP_DIR}" || exit 1
fi

# POSSIBLE doc_types: config map canvas-workpad canvas-element index-pattern visualization search dashboard url
# NOTE: If there are no objects available in Kibana, don't break the script.
for doc_type in visualization dashboard; do
    curl -X POST "${KIBANA_HOST}/api/saved_objects/_export" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{
        "type": "'"$doc_type"'",
        "excludeExportDetails": true,
        "includeReferencesDeep": false
    }' > "${BACKUP_DIR}/${doc_type}.ndjson" || true
done
