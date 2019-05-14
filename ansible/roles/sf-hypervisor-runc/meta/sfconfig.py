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


class HypervisorRunC(Component):
    role = "hypervisor-runc"

    def argparse(self, args):
        if args.enable_insecure_slaves:
            args.glue["enable_insecure_slaves"] = True

    def validate(self, args, host):
        if host["roles"] != ["hypervisor-runc"] and \
           args.glue.get("enable_insecure_slaves") is not True:
            print("Can not deploy hypervisor-runc on %s" % host["hostname"])
            print("This host is part of the control-plane, use "
                  "--enable-insecure-slaves argument to continue. ")
            print("See https://softwarefactory-project.io/docs/operator/"
                  "nodepool_operator.html#container-provider")
            exit(1)

    def prepare(self, args):
        # Create the runc structure based on nodepool.runc_nodes configuration
        args.glue.setdefault("runc", {})
        for host in args.sfarch["inventory"]:
            if "hypervisor-runc" in host["roles"]:
                self.create_nodes(args, host)

    def create_nodes(self, args, host):
        args.glue["runc"][host['hostname']] = []
        port = int(args.glue.get("runc_start_port", 22000))
        for runc_node in args.sfconfig["nodepool"].get("runc_nodes", []):
            for idx in range(runc_node["count"]):
                if runc_node.get("rootfs", "/") == "/":
                    runc_node["rootfs"] = "/srv/host-rootfs"
                args.glue["runc"][host['hostname']].append({
                    'label': runc_node['label'],
                    'rootfs': runc_node['rootfs'],
                    'port': port
                })
                port += 1
