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


class HypervisorK1s(Component):
    role = "hypervisor-k1s"

    def argparse(self, args):
        if args.enable_insecure_workers:
            args.glue["enable_insecure_workers"] = True

    def configure(self, args, host):
        self.get_or_generate_cert(args, "k1s", "localhost")

    def validate(self, args, host):
        if host["roles"] != ["hypervisor-k1s"] and \
           args.glue.get("enable_insecure_workers") is not True:
            print("Can not deploy hypervisor-k1s on %s" % host["hostname"])
            print("This host is part of the control-plane, use "
                  "--enable-insecure-workers argument to continue.")
            print("See https://softwarefactory-project.io/docs/operator/"
                  "nodepool_operator.html#container-provider")
            exit(1)
