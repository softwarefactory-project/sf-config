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

import os

from sfconfig.components import Component
from sfconfig.utils import fail


class NodepoolBuilder(Component):
    role = "nodepool-builder"
    require_roles = ["zookeeper"]

    def configure(self, args, host):
        args.glue["nodepool_hosts"].append(host["hostname"])


class NodepoolLauncher(Component):
    role = "nodepool-launcher"
    require_roles = ["zookeeper"]

    def configure(self, args, host):
        args.glue["nodepool_providers"] = args.sfconfig.get(
            "nodepool", {}).get("providers", [])
        args.glue["nodepool_dib_reg_passwords"] = args.sfconfig.get(
            "nodepool", {}).get("dib_reg_passwords", [])
        args.glue["nodepool_clouds_file"] = args.sfconfig.get(
            "nodepool", {}).get("clouds_file", None)
        if args.glue["nodepool_clouds_file"]:
            if not os.path.isfile(args.glue["nodepool_clouds_file"]):
                fail("%s: does not exists" % args.glue["nodepool_clouds_file"])
        if args.glue["nodepool_providers"] and args.glue[
                "nodepool_clouds_file"]:
            fail("Both clouds_file and providers can not be set "
                 "at the same time")

        args.glue["nodepool_kube_file"] = args.sfconfig.get(
            "nodepool", {}).get("kube_file", None)
        if args.glue["nodepool_kube_file"]:
            if not os.path.isfile(args.glue["nodepool_kube_file"]):
                fail("%s: does not exists" % args.glue["nodepool_kube_file"])

        args.glue["nodepool_ibm_credentials"] = args.sfconfig.get(
            "nodepool", {}).get("ibm_credentials_file", None)
        if args.glue["nodepool_ibm_credentials"]:
            if not os.path.isfile(args.glue["nodepool_ibm_credentials"]):
                fail("%s: does not exists" %
                     args.glue["nodepool_ibm_credentials"])

        args.glue["nodepool_aws_file"] = args.sfconfig.get(
            "nodepool", {}).get("aws_file", None)
        if args.glue["nodepool_aws_file"]:
            if not os.path.isfile(args.glue["nodepool_aws_file"]):
                fail("%s: does not exists" % args.glue["nodepool_aws_file"])

        self.get_or_generate_ssh_key(args, "nodepool_rsa")
        self.get_or_generate_ssh_key(args, "zuul_rsa")

        # nodepool_openshift_providers is only used to hold managed clusters
        args.glue["nodepool_openshift_providers"] = []
        for host in args.sfarch['inventory']:
            if 'hypervisor-openshift' in host['roles']:
                args.glue["nodepool_openshift_providers"].append({
                    "url": "https://%s:8443" % host['hostname'],
                    "hostname": host['hostname'],
                    "context": "local-%s" % host['hostname'].replace('.', '-'),
                    "max_servers": host.get('max-servers', 10),
                    "insecure_skip_tls_verify": True,
                })
