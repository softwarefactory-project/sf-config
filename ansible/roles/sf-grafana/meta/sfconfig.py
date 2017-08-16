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


class Grafana(Component):
    def configure(self, args, host):
        args.glue["grafana_internal_url"] = "http://%s:%s" % (
            args.glue["grafana_host"], args.defaults["grafana_http_port"])
        self.add_mysql_database(args, "grafana")
