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


class LogStash(Component):
    def configure(self, args, host):
        if 'retention_days' in args.sfconfig['logstash']:
            args.glue['logstash_retention_days'] = \
                args.sfconfig['logstash']['retention_days']
        if 'minimum_heap_size' in args.sfconfig['logstash']:
            args.glue['logstash_minimum_heap_size'] = args.sfconfig[
                'logstash']['minimum_heap_size']
        if 'maximum_heap_size' in args.sfconfig['logstash']:
            args.glue['logstash_maximum_heap_size'] = args.sfconfig[
                'logstash']['maximum_heap_size']

        config_key = 'external_elasticsearch'
        args.glue['external_elasticsearch_suffix'] = \
            args.sfconfig.get(config_key, {}).get('suffix')
        args.glue['external_elasticsearch_host'] = \
            args.sfconfig.get(config_key, {}).get('host')
        args.glue['external_elasticsearch_cacert'] = \
            args.sfconfig.get(config_key, {}).get('cacert_path')
        args.glue['external_elasticsearch_users'] = \
            args.sfconfig.get(config_key, {}).get('users')
