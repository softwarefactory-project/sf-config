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
[ -z "$SCP_BACKUP_RET" ] && exit 0
[ -z "$SCP_BACKUP_HOST" ] && exit 0
[ -z "$SCP_BACKUP_PORT" ] && exit 0
[ -z "$SCP_BACKUP_DIRECTORY" ] && exit 0

RETENTION_SECS=${SCP_BACKUP_RET}

epoch=$(date +%s)

echo "Backup started at ${epoch}."

# Create the remote directory if it does not exist
ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} "ls $SCP_BACKUP_DIRECTORY" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "Create directory ${SCP_BACKUP_DIRECTORY}."
    ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} "mkdir -p ${SCP_BACKUP_DIRECTORY}"
fi

# Clean old backups if needed
backups=$(ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} "ls $SCP_BACKUP_DIRECTORY" 2>/dev/null | sort)
count=$(echo $backups | wc -w)
echo "Directory ${SCP_BACKUP_DIRECTORY} has $count backups before deletion."
for backup in $backups; do
    upload_date=$(ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} "ls -l --time-style='+%s' ${SCP_BACKUP_DIRECTORY}/${backup}" 2>/dev/null | awk '{print $6}')
    if [ $((epoch - upload_date)) -gt $RETENTION_SECS ]; then
        if [ $count -gt 5 ]; then
            echo "Backup $backup is too old according to the retention value. Delete it."
            ssh -p ${SCP_BACKUP_PORT} ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST} "rm ${BACKUP_DIR}/$backup" || {
                echo "Deleting backup $backup from ${SCP_BACKUP_DIRECTORY} failed."
            }
            let count=count-1
        fi
    fi
done

# Create backup
ansible-playbook /var/lib/software-factory/ansible/sf_backup.yml -e create_tarball=$(pwd)/sf_backup.tar.gz
# Encrypt backup
[ -e sf_backup.tar.gz.gpg ] && rm sf_backup.tar.gz.gpg
gpg --homedir /root/.gnupg/ -e -r sfadmin --trust-model always sf_backup.tar.gz
# Rename to include timestamp
mv sf_backup.tar.gz.gpg sf_backup_${epoch}.tar.gz.gpg
# Upload
scp -P ${SCP_BACKUP_PORT} sf_backup_${epoch}.tar.gz.gpg ${SCP_BACKUP_USER}@${SCP_BACKUP_HOST}:${SCP_BACKUP_DIRECTORY}

if [ "$?" != "0" ]; then
    echo "Error when uploading the backup sf_backup_${epoch}.tar.gz to ${SCP_BACKUP_DESTINATION}! exit."
    exit 1
fi

# Remove local file
rm sf_backup_${epoch}.tar.gz.gpg

echo "sf_backup_${epoch}.tar.gz has been backed up."
