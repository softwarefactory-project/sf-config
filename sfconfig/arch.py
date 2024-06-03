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

import copy
import sys
from sfconfig.utils import pread
from sfconfig.utils import fail

required_roles = (
    "install-server",
    "gateway",
    "mysql",
    "managesf",
    "keycloak",
)

rhel_unsupported_roles = (
    "firehose",
)

correct_order = ['gerrit', 'managesf', 'opensearch', 'opensearch-dashboards']


def combine_common_hosts(inventory):
    # Combined the hosts that runs the same executor/merger roles
    inventory = copy.deepcopy(inventory)
    combined_hosts = set()

    def combine_host(host, role):
        # Collect all the host with this role setup
        matching_hosts = list(
            map(lambda x: x['hostname'],
                filter(lambda x: x['roles'] == [role], inventory)))
        # Modify the given host to match all the hosts
        host['hostname'] = ':'.join(matching_hosts)
        if len(matching_hosts) > 1:
            # Register all the duplicated hosts
            combined_hosts.update(matching_hosts)

    for host in inventory:
        if host['hostname'] not in combined_hosts:
            for combinable in ["zuul-executor", "zuul-merger"]:
                if host['roles'] == [combinable]:
                    combine_host(host, combinable)

    return list(filter(
        lambda x: x['hostname'] not in combined_hosts, inventory))


def process(args):
    # scalable_roles are the roles that can be instantiate multiple time
    # this indicate that we don't need $role.$fqdn aliases
    # TODO: remove this logic when $role.$fqdn are no longer used
    args.glue["scalable_roles"] = [
        "zuul",
        "zuul-merger",
        "zuul-executor",
        "zuul-fingergw",
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

        # NOTE: Remove the condition when move name from elasticsearch to
        # opensearch is done
        if 'elasticsearch' in host['roles']:
            host['roles'] = [r.replace('elasticsearch',
                                       'opensearch') for r in host['roles']]

        if 'kibana' in host['roles']:
            host['roles'] = [r.replace('kibana',
                                       'opensearch') for r in host['roles']]

        if 'cauth' in host['roles']:
            host['roles'] = [r.replace('cauth',
                                       'keycloak') for r in host['roles']]

        for role in host["roles"]:
            # Add host to role list
            args.glue["roles"].setdefault(role, []).append(host)
            # Add extra aliases for specific roles
            if role == "gateway":
                aliases.add(args.sfconfig["fqdn"])
            elif role not in args.glue["scalable_roles"]:
                # Add role name virtual name (as cname)
                aliases.add("%s.%s" % (role, args.sfconfig["fqdn"]))
                aliases.add(role)
            # Check if this is the first nodepool-launcher
            if role == "nodepool-launcher" and not args.glue["first_launcher"]:
                args.glue["first_launcher"] = host['name']

        if args.sfconfig.get('external_opensearch', {}):
            if 'opensearch' in aliases:
                aliases.remove('opensearch')
                aliases.remove("opensearch.%s" % args.sfconfig["fqdn"])

        if "public_ip" in host:
            args.glue["public_hosts_file"][host["public_ip"]] = \
                [host["hostname"]] + list(aliases)
        else:
            args.glue["public_hosts_file"][host["ip"]] = [host["hostname"]] + \
                list(aliases)

        args.glue["hosts_file"][host["ip"]] = [host["hostname"]] + \
            list(sorted(aliases))

        # NOTE(dpawlik) Remove it after moving elasticsearch role to opensearch
        if 'elasticsearch' in aliases:
            aliases.add("%s.%s" % ('opensearch', args.sfconfig["fqdn"]))
            aliases.add("opensearch")

        if 'kibana' in aliases:
            aliases.add("%s.%s" % ('opensearch-dashboards',
                                   args.sfconfig["fqdn"]))
            aliases.add("opensearch-dashboards")

        # Check if inventory role order is correct
        correct_order_indexes = []
        for role in correct_order:
            if role in host["roles"]:
                correct_order_indexes.append(host["roles"].index(role))

        if sorted(correct_order_indexes) != correct_order_indexes:
            print("There is wrong order set in roles. Please change it to:")
            for role_index in correct_order_indexes:
                print("- %s" % host["roles"][role_index])
            print("Current host roles are:")
            for role in host["roles"]:
                print("- %s" % role)
            sys.exit(1)

    args.sfarch["combined_inventory"] = combine_common_hosts(
        args.sfarch["inventory"])

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

    if (args.sfconfig.get('external_opensearch', {}) and (
            not args.sfconfig['external_opensearch'].get('users') or
            not args.sfconfig['external_opensearch'].get('host') or
            not args.sfconfig['external_opensearch'].get('cacert_path') or
            not args.sfconfig['external_opensearch'].get('suffix'))):
        print('Some of "external_opensearch" params are missing. Please '
              'check Software Factory document and provide required '
              'parameters')
        sys.exit(1)

    if (args.sfconfig.get('external_opensearch', {}) and not (
            args.sfconfig.get('zuul').get('opensearch_connections'))):
        print('You did not configure "opensearch_connections" param '
              'in zuul configuration in sfconfig.yaml file. Is it ok?')
        sys.exit(1)

    # Add install-server hostname for easy access
    args.glue["install_server"] = args.glue["roles"]["install-server"][0][
        "hostname"]
