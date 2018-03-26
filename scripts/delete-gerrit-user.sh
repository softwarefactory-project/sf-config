#!/bin/bash
# Copyright (C) 2018 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

USERNAME=$1

if [ -z "${USERNAME}" ]; then
    echo "usage: $0 username";
    exit 1;
fi

ACCOUNT_ID=$(mysql gerrit --skip-column-names -e "select accounts.account_id"\
" from accounts, account_external_ids where"\
" account_external_ids.external_id = 'username:${USERNAME}'"\
" and accounts.account_id = account_external_ids.account_id")
if [ -z "${ACCOUNT_ID}" ]; then
    echo "User ${USERNAME} not found"
    exit 1
fi
if [ "$2" != "--batch" ]; then
    echo "Are you sure? (Gerrit restart is needed)."
    echo "Going to remove ${USERNAME} (id: ${ACCOUNT_ID}), press C-c to cancel"
    read
else
    echo "Going to remove ${USERNAME} (id: ${ACCOUNT_ID})"
fi

systemctl stop gerrit
echo "User account id = ${ACCOUNT_ID}"
mysql gerrit \
    -e "DELETE FROM account_group_members WHERE account_id=${ACCOUNT_ID};" \
    -e "DELETE FROM accounts WHERE account_id=${ACCOUNT_ID};"              \
    -e "DELETE FROM account_external_ids WHERE account_id=${ACCOUNT_ID};"
sudo -u gerrit /usr/bin/java -jar /usr/lib64/gerrit/release.war reindex \
     -d /var/lib/gerrit
systemctl start gerrit
echo "Done"
