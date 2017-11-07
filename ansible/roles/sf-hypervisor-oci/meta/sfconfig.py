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


class HypervisorOci(Component):
    role = "hypervisor-oci"

    def usage(self, parser):
        parser.add_argument("--enable-insecure-slaves", action='store_true',
                            help="Allow using hypervisor-oci on the "
                            "control plane")

    def argparse(self, args):
        if args.enable_insecure_slave:
            args.glue["enable_insecure_slaves"] = True

    def validate(self, args, host):
        if host["roles"] != ["hypervisor-oci"] and \
           args.glue.get("enable_insecure_slaves") is not True:
            print("Can not deploy hypervisor-oci on %s" % host["hostname"])
            print("This host is part of the control-plane, use "
                  "--enable-insecure-slaves argument to continue. ")
            print("See https://softwarefactory-project.io/docs/operator/"
                  "nodepool_operator.html#container-provider")
            exit(1)
