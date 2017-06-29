#!/bin/bash

# Copyright (C) 2017 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

[ -n "$DEBUG" ] && set -x
set -e
export HOME=/root
cd ${HOME}

. /etc/auto_backup.conf

# Exit silently if we don"t have enough SCP_BACKUP_* env vars
[ -z "$SCP_BACKUP_USER" ] && exit 0
[ -z "$SCP_BACKUP_HOST" ] && exit 0
[ -z "$SCP_BACKUP_PORT" ] && exit 0
[ -z "$SCP_BACKUP_DIRECTORY" ] && exit 0

BACKUP_SOURCE_DIR=/var/lib/software-factory/backup/

echo "Export of ${BACKUP_SOURCE_DIR} started at $(date +%s)."
ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} mkdir -p ${SCP_BACKUP_DIRECTORY}
rsync -az --delete --stats -h -e "ssh -p ${SCP_BACKUP_PORT}" \
  /var/lib/software-factory/backup/ ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST}:${SCP_BACKUP_DIRECTORY}
echo "Export of ${BACKUP_SOURCE_DIR} ended at $(date +%s)."
