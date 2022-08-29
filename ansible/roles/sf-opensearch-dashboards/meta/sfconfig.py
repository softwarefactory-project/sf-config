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


class Kibana(Component):
    def configure(self, args, host):

        if 'kibana' in args.sfconfig:
            args.glue['readonly_user_autologin'] = \
                args.sfconfig.get("kibana", {}).get('readonly_user_autologin',
                                                    'Basic')
        elif 'opensearch_dashboards' in args.sfconfig:
            args.glue['readonly_user_autologin'] = \
                args.sfconfig.get("opensearch_dashboards", {}).get(
                    'readonly_user_autologin', 'Basic')

        self.get_or_generate_cert(args, "opensearch-dashboards",
                                  host["hostname"])
