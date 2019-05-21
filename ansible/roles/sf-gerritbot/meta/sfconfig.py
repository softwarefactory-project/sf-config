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


class Gerritbot(Component):
    def configure(self, args, host):
        self.get_or_generate_ssh_key(args, "zuul_rsa")
        conn = args.sfconfig.get("gerritbot", {}).get("gerrit")
        if conn:
            # Lookup zuul gerrit connection
            gerrit_conn = list(
                filter(lambda x: x["name"] == conn,
                       args.glue["zuul_gerrit_connections"]))[0]
            if not gerrit_conn:
                raise RuntimeError("%s: unknown gerrit connection" % conn)
            gerrit_user, gerrit_host, gerrit_port = (
                gerrit_conn["username"], gerrit_conn["hostname"],
                gerrit_conn.get("port", 29418))
        else:
            gerrit_user, gerrit_host, gerrit_port = "zuul", "gerrit", 29418
        args.glue["gerritbot_gerrit_user"] = gerrit_user
        args.glue["gerritbot_gerrit_host"] = gerrit_host
        args.glue["gerritbot_gerrit_port"] = int(gerrit_port)
