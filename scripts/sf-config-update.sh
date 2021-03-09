#!/bin/bash
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

STRINGARRAY=($SSH_ORIGINAL_COMMAND)
ACTION="${STRINGARRAY[0]}"
COMMIT="${STRINGARRAY[1]}"

export ANSIBLE_CONFIG=/var/lib/software-factory/ansible/ansible.cfg
export ZUUL_COMMIT="$COMMIT"

if [ -n "$ZUUL_COMMIT" ]; then
    echo "Triggered by commit: $ZUUL_COMMIT"
else
    echo "Triggered outside of Zuul (No ZUUL_COMMIT provided)"
fi

LOCK_PATH=/var/lib/software-factory/state/ansible.lock

case $ACTION in
    sf_configrepo_update)
        set -o pipefail
        exec flock $LOCK_PATH ansible-playbook -v /var/lib/software-factory/ansible/sf_configrepo_update.yml 2>&1 | tee /var/log/software-factory/configrepo_update.log
        ;;
    sf_tenant_update)
        set -o pipefail
        exec flock $LOCK_PATH ansible-playbook -v /var/lib/software-factory/ansible/sf_tenant_update.yml 2>&1 | tee /var/log/software-factory/tenant_update.log
        ;;
    *)
        echo "NotImplemented"
        exit -1
esac
