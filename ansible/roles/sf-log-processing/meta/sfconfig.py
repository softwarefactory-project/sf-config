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

import urllib.parse

from sfconfig.components import Component


class LogProcessing(Component):
    def configure(self, args, host):
        external_elk = args.sfconfig.get('external_opensearch', {})

        host = external_elk.get('host', None)
        args.glue['external_opensearch_host'] = \
            urllib.parse.urlparse(host).hostname if host else None
        args.glue['external_opensearch_port'] = \
            urllib.parse.urlparse(host).port if host else None

        if external_elk.get('cacert_path', None):
            args.glue['external_opensearch_cacert'] = \
                external_elk.get('cacert_path')

        if external_elk.get('users', None):
            args.glue['external_opensearch_users'] = \
                external_elk.get('users')
