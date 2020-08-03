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


class ElasticSearch(Component):
    def configure(self, args, host):
        if 'minimum_heap_size' in args.sfconfig['elasticsearch']:
            args.glue['elasticsearch_minimum_heap_size'] = args.sfconfig[
                'elasticsearch']['minimum_heap_size']
        if 'maximum_heap_size' in args.sfconfig['elasticsearch']:
            args.glue['elasticsearch_maximum_heap_size'] = args.sfconfig[
                'elasticsearch']['maximum_heap_size']
        if 'replicas' in args.sfconfig['elasticsearch']:
            args.glue['elasticsearch_replicas'] = args.sfconfig[
                'elasticsearch']['replicas']

        self.get_or_generate_cert(args, "elasticsearch-admin",
                                  host["hostname"])
