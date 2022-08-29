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

from sfconfig.components import Component


class OpensSearch(Component):
    def configure(self, args, host):
        if 'minimum_heap_size' in args.sfconfig['opensearch']:
            args.glue['opensearch_minimum_heap_size'] = args.sfconfig[
                'opensearch']['minimum_heap_size']
        if 'maximum_heap_size' in args.sfconfig['opensearch']:
            args.glue['opensearch_maximum_heap_size'] = args.sfconfig[
                'opensearch']['maximum_heap_size']
        if 'replicas' in args.sfconfig['opensearch']:
            args.glue['opensearch_replicas'] = args.sfconfig[
                'opensearch']['replicas']

        self.get_or_generate_cert(args, "opensearch-admin",
                                  host["hostname"])

        # The internal Elasticsearch connection should not be included in
        # sfconfig. Add other connections that will be used by zuul.
        args.glue["opensearch_connections"].append({
                    'name': "opensearch",
                    'username': 'zuul',
                    'password': args.defaults['opensearch_zuul_password'],
                    'host': args.glue["opensearch_host"],
                    'port': args.defaults["opensearch_http_port"],
                })

        args.glue["opensearch_connections"] = [dict(t) for t in {
            tuple(d.items()) for d in args.glue["opensearch_connections"]}]

        args.glue['readonly_user_autologin'] = \
            args.sfconfig.get("opensearch_dashboards", {}).get(
                'readonly_user_autologin', 'Basic')
