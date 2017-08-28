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

from sfconfig.utils import pread
from sfconfig.utils import fail

required_roles = (
    "install-server",
    "gateway",
    "mysql",
)


def process(args):
    # roles is a dictwith roles name as key and host list as value
    args.glue["roles"] = {}

    # hosts_files is a dict with host ip as key and hostname list as value
    args.glue["hosts_file"] = {}

    for host in args.sfarch["inventory"]:
        if "install-server" in host["roles"]:
            host["ip"] = pread(["ip", "route", "get", "8.8.8.8"]).split()[6]
        elif "ip" not in host:
            fail("%s: host '%s' needs an ip" % (args.arch, host["name"]))

        if "public_url" not in host:
            if "gateway" in host["roles"]:
                host["public_url"] = "https://%s" % args.sfconfig["fqdn"]
            else:
                host["public_url"] = "http://%s" % host["ip"]
        else:
            host["public_url"] = host["public_url"].rstrip("/")

        args.glue["hosts_file"][host["ip"]] = [host["hostname"]]

    # Check roles
    for requirement in required_roles:
        if requirement not in args.glue["roles"]:
            fail("%s role is missing" % requirement)
        if len(args.glue["roles"][requirement]) > 1:
            fail("Only one instance of %s is required" % requirement)

    # Add gateway and install-server hostname/ip for easy access
    gateway_host = args.glue["roles"]["gateway"][0]
    install_host = args.glue["roles"]["install-server"][0]
    args.glue["gateway"] = gateway_host["hostname"]
    args.glue["gateway_ip"] = gateway_host["ip"]
    args.glue["install"] = install_host["hostname"]
    args.glue["install_ip"] = install_host["ip"]
