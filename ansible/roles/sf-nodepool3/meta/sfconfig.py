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


class Nodepool3Launcher(Component):
    role = "nodepool3-launcher"
    require_roles = ["zookeeper"]

    def configure(self, args, host):
        args.glue["nodepool3_providers"] = args.sfconfig.get(
            "nodepool3", {}).get("providers", [])
        self.get_or_generate_ssh_key(args, "nodepool_rsa")
        self.get_or_generate_ssh_key(args, "zuul_rsa")
        args.glue["nodepool3_internal_url"] = "http://%s:%s" % (
            args.glue["nodepool3_launcher_host"],
            args.defaults["nodepool3_webapp_port"])
        args.glue["nodepool3_admin_internal_url"] = "http://%s:%s" % (
            args.glue["nodepool3_launcher_host"],
            args.defaults["nodepool3_admin_webapp_port"])
