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

if [ "$2" != "--batch" ]; then
    echo "Are you sure? (Gerrit restart is needed)."
    echo "Going to remove ${USERNAME}, press C-c to cancel"
    read
else
    echo "Going to remove ${USERNAME}"
fi

systemctl stop gerrit
sudo -u gerrit /usr/local/bin/pynotedb delete-user \
--all-users /var/lib/gerrit/git/All-Users.git \
--name ${USERNAME} --email ${EMAIL}
systemctl start gerrit
echo "Done"
