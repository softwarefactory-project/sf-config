#!/bin/bash

KIBANA_HOST=${KIBANA_HOST:-'localhost:5601'}
BACKUP_DIR=${KIBANA_BACKUP_DIR:-'/usr/share/sf-config/kibana-backup'}

# POSSIBLE doc_types: config map canvas-workpad canvas-element index-pattern visualization search dashboard url
for doc_type in visualization dashboard;
do
    curl -X POST "${KIBANA_HOST}/api/saved_objects/_export" -H 'kbn-xsrf: true' -H 'Content-Type: application/json' -d '{
        "type": "'"$doc_type"'",
        "excludeExportDetails": true,
        "includeReferencesDeep": true
    }' > "${BACKUP_DIR}/${doc_type}.ndjson"
done
