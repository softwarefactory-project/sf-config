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


class Zookeeper(Component):
    role = "zookeeper"

    def configure(self, args, host):
        self.get_or_generate_cert(args, "zk_client", "client")
        self.get_or_generate_cert(
            args, "zk_" + host["name"], host["hostname"])
        # Combine certs for zookeeper configuration needs
        if "zk_keys" not in args.glue:
            args.glue["zk_keys"] = dict()
        args.glue["zk_keys"][host["hostname"]] = (
            args.glue["zk_" + host["name"] + "_crt"] +
            args.glue["zk_" + host["name"] + "_key"])
