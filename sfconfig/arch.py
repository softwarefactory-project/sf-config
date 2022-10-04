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
)

rhel_unsupported_roles = (
    "firehose",
)

correct_order = ['gerrit', 'managesf', 'elasticsearch', 'logstash', 'kibana']


def process(args):
    # scalable_roles are the roles that can be instantiate multiple time
    # this indicate that we don't need $role.$fqdn aliases
    # TODO: remove this logic when $role.$fqdn are no longer used
    args.glue["scalable_roles"] = [
        "zuul",
        "zuul-merger",
        "zuul-executor",
        "nodepool-launcher",
        "hypervisor-k1s",
    ]

    # roles is a dictwith roles name as key and host list as value
    args.glue["roles"] = {}

    # hosts is a list of hostname
    args.glue["launcher_hosts"] = []
    args.glue["first_launcher"] = ""

    # hosts_files is a dict with host ip as key and hostname list as value
    args.glue["hosts_file"] = {}
    args.glue["public_hosts_file"] = {}

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

        if "nodepool-launcher" in host["roles"]:
            args.glue["launcher_hosts"].append(host['name'])

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

        if "public_ip" in host:
            args.glue["public_hosts_file"][host["public_ip"]] = \
                [host["hostname"]] + list(aliases)
        else:
            args.glue["public_hosts_file"][host["ip"]] = [host["hostname"]] + \
                list(aliases)

        args.glue["hosts_file"][host["ip"]] = [host["hostname"]] + \
            list(aliases)

        # Check if inventory role order is correct
        correct_order_indexes = []
        for role in correct_order:
            if role in host["roles"]:
                correct_order_indexes.append(host["roles"].index(role))

        if sorted(correct_order_indexes) != correct_order_indexes:
            print("There is wrong order set in roles. Please change it to:")
            for role_index in correct_order_indexes:
                print("- %s" % host["roles"][role_index])
            sys.exit(1)

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

    if (all(x in args.glue["roles"] for x in ['cauth', 'keycloak']) or
       all(x not in args.glue["roles"] for x in ['cauth', 'keycloak'])):
        fail("Either 'keycloak' OR 'cauth' component is needed")

    # TODO remove this at the end of the patch chain
    if 'keycloak' in args.glue["roles"]:
        print("/!\\ keycloak is not completely supported at this point."
              "Deploying Software Factory with this role will lead to "
              "failures. Do it only for testing things out!")

    if ('logstash' in args.glue["roles"] and
        'elasticsearch' not in args.glue["roles"] and
            not args.sfconfig.get('external_elasticsearch')):
        print('Can not continue. You need to provide elasticsearch role '
              'or add external_elasticsearch configuration in sfconfig '
              'file if you want to use logstash')
        sys.exit(1)

    if (args.sfconfig.get('external_elasticsearch', {}) and (
            not args.sfconfig['external_elasticsearch'].get('users') or
            not args.sfconfig['external_elasticsearch'].get('host') or
            not args.sfconfig['external_elasticsearch'].get('cacert_path') or
            not args.sfconfig['external_elasticsearch'].get('suffix'))):
        print('Some of "external_elasticsearch" params are missing. Please '
              'check Software Factory document and provide required '
              'parameters')
        sys.exit(1)

    if ('logstash' in args.glue["roles"] and args.sfconfig.get(
        'external_elasticsearch', {}) and not (
            args.sfconfig.get('zuul').get('elasticsearch_connections'))):
        print('You did not configure "elasticsearch_connections" param '
              'in zuul configuration in sfconfig.yaml file. Is it ok?')
        sys.exit(1)

    if ('logstash' in args.glue["roles"] and
            args.sfconfig.get('logstash').get('host', None)):
        print('Multiple Logstash configuration found. Please remove '
              '"logstash" role from arch file or remove "host" from logstash '
              'section in sfconfig.yaml file!')
        sys.exit(1)

    # Add install-server hostname for easy access
    args.glue["install_server"] = args.glue["roles"]["install-server"][0][
        "hostname"]
