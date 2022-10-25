#!/bin/sh
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

# Use this script to manually recreate any users from the local user backend
# (ie created with sfmanager) into Keycloak.
# Note that passwords cannot be dumped, so the users are provisioned without
# credentials.

# Usage: ./sfusers_to_keycloak.sh

SQL="select username, email, fullname, sshkey from users;"
ADMIN_PASSWORD=$(cat /var/lib/software-factory/ansible/group_vars/all.yaml | grep " admin_password:" | awk '{print $2}')
MANAGESF_PASSWORD=$(cat /var/lib/software-factory/ansible/group_vars/all.yaml | grep managesf_mysql_password | awk '{print $2}')

USERS=$(podman exec mysql mysql managesf -umanagesf -p${MANAGESF_PASSWORD} --default-character-set=utf8 -N -B -e "$SQL")

echo "The following users will be provisioned without password, as only hashes are stored in the local database:"
echo "$USERS"
echo " A password can be added later via the admin GUI console or by using the \"Forgotten Password\" form on the login page."

i=0
echo "$USERS" | while IFS=$'\t' read -r uname email fullname sshkey ; do
    echo "Creating user ${uname}..."
    podman exec -t keycloak /opt/jboss/keycloak/bin/kcadm.sh create users \
        -r SF \
        -s "username=${uname}" \
        -s "email=${email}" \
        -s "firstName=${fullname}" \
        -s "attributes.publicKey=[\"${sshkey}\"]" \
        -s "enabled=true" \
        -s "requiredActions=[\"UPDATE_PASSWORD\", \"VERIFY_EMAIL\"]" \
        --no-config \
        --password ${ADMIN_PASSWORD} \
        --realm master \
        --server http://localhost:38080/auth \
        --user admin
    sleep 1
done
