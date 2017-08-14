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

from sfconfig.utils import fail
from sfconfig.utils import yaml_load

required_roles = (
    "install-server",
    "gateway",
    "mysql",
)


def load(filename, domain=None, install_server_ip=None):
    arch = yaml_load(filename)
    # Update domain
    if domain:
        arch["domain"] = domain
    # scalable_roles are the roles that can be instantiate multiple time
    arch["scalable_roles"] = [
        "zuul", "zuul-merger", "zuul-launcher",
        "zuul3", "zuul3-merger", "zuul3-executor",
    ]
    # roles is a dictwith roles name as key and host list as value
    arch["roles"] = {}
    # hosts_files is a dict with host ip as key and hostname list as value
    arch["hosts_file"] = {}
    for host in arch["inventory"]:
        if install_server_ip and "install-server" in host["roles"]:
            host["ip"] = install_server_ip
        elif "ip" not in host:
            fail("%s: host '%s' needs an ip" % (filename, host["name"]))

        if "public_url" not in host:
            if "gateway" in host["roles"]:
                host["public_url"] = "https://%s" % domain
            else:
                host["public_url"] = "http://%s" % host["ip"]
        else:
            host["public_url"] = host["public_url"].rstrip("/")

        host["hostname"] = "%s.%s" % (host["name"], arch["domain"])
        # aliases is a list of cname for this host.
        aliases = set((host['name'],))
        for role in host["roles"]:
            # Add host to role list
            arch["roles"].setdefault(role, []).append(host)
            # Add extra aliases for specific roles
            if role == "gateway":
                aliases.add(arch['domain'])
            elif role == "cauth":
                aliases.add("auth.%s" % arch['domain'])
            elif role not in arch["scalable_roles"]:
                # Add role name virtual name (as cname)
                aliases.add("%s.%s" % (role, arch["domain"]))
                aliases.add(role)
        arch["hosts_file"][host["ip"]] = [host["hostname"]] + list(aliases)

    # Check roles
    for requirement in required_roles:
        if requirement not in arch["roles"]:
            fail("%s role is missing" % requirement)
        if len(arch["roles"][requirement]) > 1:
            fail("Only one instance of %s is required" % requirement)

    # Auto adds mandatory roles
    for role in ("zuul-launcher", "logserver"):
        if role not in arch["roles"]:
            print("Adding missing %s role" % role)
            host = arch["inventory"][0]
            host["roles"].append(role)
            arch["roles"].setdefault(role, []).append(host)
    # Adds zookeeper if nodepool-launcher is enabled
    if "nodepool" in arch["roles"] or "nodepool-launcher" in arch["roles"]:
        if "zookeeper" not in arch["roles"]:
            print("Adding missing zookeeper role")
            host = arch["inventory"][0]
            host["roles"].append("zookeeper")
            arch["roles"].setdefault("zookeeper", []).append(host)

    # Add gateway and install-server hostname/ip for easy access
    gateway_host = arch["roles"]["gateway"][0]
    install_host = arch["roles"]["install-server"][0]
    arch["gateway"] = gateway_host["hostname"]
    arch["gateway_ip"] = gateway_host["ip"]
    arch["install"] = install_host["hostname"]
    arch["install_ip"] = install_host["ip"]
    return arch
