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

set -x
set -e

# Only execute that if the config repository does not embed replication.config yet
if [ ! -f /root/config/gerrit/replication.config ]; then
    mkdir /root/config/gerrit || true
    cp /etc/gerrit/replication.config /root/config/gerrit/
    cd /root/config
    if [ -n "$(git ls-files -o -m --exclude-standard)" ]; then
        git add -A
        git commit -m "Add gerrit/replication.config in the config repository"
        git review -i
    fi
fi
