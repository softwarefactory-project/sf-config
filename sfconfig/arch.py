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

import sys
from sfconfig.utils import pread
from sfconfig.utils import fail

required_roles = (
    "install-server",
    "gateway",
    "mysql",
    "managesf",
    "cauth",
)

rhel_unsupported_roles = (
    "dlrn",
    "firehose",
    "hydrant",
)


def process(args):
    # scalable_roles are the roles that can be instantiate multiple time
    # this indicate that we don't need $role.$fqdn aliases
    # TODO: remove this logic when $role.$fqdn are no longer used
    args.glue["scalable_roles"] = [
        "zuul",
        "zuul-merger",
        "zuul-executor",
        "nodepool-launcher",
        "hypervisor-runc",
    ]

    # roles is a dictwith roles name as key and host list as value
    args.glue["roles"] = {}

    # hosts is a list of hostname
    args.glue["hosts"] = []
    args.glue["first_launcher"] = ""

    # hosts_files is a dict with host ip as key and hostname list as value
    args.glue["hosts_file"] = {}

    for host in args.sfarch["inventory"]:
        if "install-server" in host["roles"]:
            host["ip"] = pread(["ip", "route", "get", "8.8.8.8"]).split()[6]
        elif "ip" not in host:
            fail("%s: host '%s' needs an ip" % (args.arch, host))

        if "public_url" not in host:
            if "gateway" in host["roles"]:
                host["public_url"] = "https://%s" % args.sfconfig["fqdn"]
            else:
                host["public_url"] = "http://%s" % host["ip"]
        else:
            host["public_url"] = host["public_url"].rstrip("/")

        args.glue["hosts"].append(host['name'])

        # TODO: remove this aliases logic when $role.$fqdn are no longer used
        aliases = set()
        if 'name' in host:
            aliases.add(host['name'])
        for role in host["roles"]:
            # Add host to role list
            args.glue["roles"].setdefault(role, []).append(host)
            # Add extra aliases for specific roles
            if role == "gateway":
                aliases.add(args.sfconfig["fqdn"])
            elif role == "cauth":
                aliases.add("auth.%s" % args.sfconfig["fqdn"])
            elif role not in args.glue["scalable_roles"]:
                # Add role name virtual name (as cname)
                aliases.add("%s.%s" % (role, args.sfconfig["fqdn"]))
                aliases.add(role)
            # Check if this is the first nodepool-launcher
            if role == "nodepool-launcher" and not args.glue["first_launcher"]:
                args.glue["first_launcher"] = host['name']
        args.glue["hosts_file"][host["ip"]] = [host["hostname"]] + \
            list(aliases)

    # Check roles
    for requirement in required_roles:
        if requirement not in args.glue["roles"]:
            fail("%s role is missing" % requirement)
        if len(args.glue["roles"][requirement]) > 1:
            fail("Only one instance of %s is required" % requirement)

    # Check if unsuported components
    if 'ID="rhel"' in open("/etc/os-release").read():
        unsupported_roles = []
        message = '''The following roles are not supported on RHEL,
please remove them from /etc/software-factory/arch.yaml file:
- %s'''
        for role in rhel_unsupported_roles:
            if role in args.glue["roles"]:
                unsupported_roles.append(role)
        if unsupported_roles:
            print(message % '\n- '.join(unsupported_roles))
            sys.exit(1)

    if len(args.sfarch["inventory"]) > 1 and (
            "cgit" not in args.glue["roles"] and
            "gerrit" not in args.glue["roles"] and
            not args.sfconfig["config-locations"]["config-repo"] and
            not args.sfconfig["config-locations"]["jobs-repo"] and
            not args.sfconfig["zuul"]["upstream_zuul_jobs"]):
        fail("Cgit or Gerrit component is required for distributed deployment")

    # Add install-server hostname for easy access
    args.glue["install_server"] = args.glue["roles"]["install-server"][0][
        "hostname"]
