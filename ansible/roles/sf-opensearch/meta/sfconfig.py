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

        # NOTE: Remove to previous state when change role name is done.
        elastic_host = (args.glue["elasticsearch_host"] if "elasticsearch_host"
                        in args.glue else args.glue["opensearch_host"])
        elastic_port = (args.defaults["elasticsearch_http_port"] if
                        "elasticsearch_http_port" in args.defaults else
                        args.defaults["opensearch_http_port"])
        elastic_zuul_pass = (args.glue['elasticsearch_zuul_password'] if
                             "elasticsearch_zuul_password" in args.glue else
                             args.glue['opensearch_zuul_password'])

        # The internal Elasticsearch connection should not be included in
        # sfconfig. Add other connections that will be used by zuul.
        args.glue["opensearch_connections"].append({
                    'name': "opensearch",
                    'username': 'zuul',
                    'password': elastic_zuul_pass,
                    'host': elastic_host,
                    'port': elastic_port,
                })

        # FIXME: remove code below after changing name from elasticsearch to
        # opensearch
        args.glue["opensearch_connections"] = [dict(t) for t in {
            tuple(d.items()) for d in args.glue["opensearch_connections"]}]

        args.glue['readonly_user_autologin'] = \
            args.sfconfig.get("kibana", {}).get('readonly_user_autologin',
                                                'Basic')
