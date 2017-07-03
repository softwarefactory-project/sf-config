# Copyright (C) 2017 Red Hat
#
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

from sfconfig.utils import fail
from sfconfig.utils import yaml_load
from sfconfig.utils import render_template

required_roles = (
    "install-server",
    "gateway",
    "mysql",
    "gerrit",
)


def load_arch(filename, domain=None, install_server_ip=None):
    arch = yaml_load(filename)
    # Update domain
    if domain:
        arch["domain"] = domain
    # scalable_roles are the roles that can be instantiate multiple time
    arch["scalable_roles"] = [
        "zuul", "zuul-merger", "zuul-launcher",
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


def generate_inventory_and_playbooks(arch, ansible_root, share):
    # Adds playbooks to architecture
    firehose = "firehose" in arch["roles"]
    for host in arch["inventory"]:
        # Generate rolesname to be used for playbook rendering
        host["rolesname"] = map(lambda x: "sf-%s" % x, host["roles"])
        # Host params are generic roles parameters
        host["params"] = {}

        # This method handles roles such as zuul-merger that are in fact the
        # zuul role with the zuul_services argument set to "merger"
        def ensure_role_services(role_name, meta_names):
            # Ensure base role exists for metarole
            for meta_name in meta_names:
                # Add role services for meta role
                service_name = "%s-%s" % (role_name, meta_name)
                if service_name in host["roles"]:
                    host["params"].setdefault(
                        "%s_services" % role_name, []).append(service_name)
                name = "sf-%s" % service_name
                # Replace meta role by real role
                if name in host["rolesname"]:
                    host["rolesname"] = list(filter(
                        lambda x: x != name, host["rolesname"]))
                    # Ensure base role is in rolesname list
                    if "sf-%s" % role_name not in host["rolesname"]:
                        host["rolesname"].append("sf-%s" % role_name)
                    # Add base role to host
                    if role_name not in host["roles"]:
                        host["roles"].append(role_name)
                    if role_name not in arch["roles"]:
                        arch["roles"].setdefault(role_name, []).append(host)

        ensure_role_services("nodepool", ["launcher", "builder"])
        ensure_role_services("zuul", ["server", "merger", "launcher"])

        # if firehose role is in the arch, install ochlero where needed
        if firehose:
            if "zuul" in host["roles"] or "nodepool" in host["roles"]:
                host["rolesname"].append("sf-ochlero")

    templates = "%s/templates" % share

    # Generate inventory
    render_template("%s/hosts" % ansible_root,
                    "%s/inventory.j2" % templates,
                    arch)

    # Generate playbooks
    for playbooks in ("sf_install", "sf_setup", "sf_postconf", "sf_upgrade",
                      "sf_configrepo_update",
                      "get_logs", "sf_backup", "sf_restore", "sf_recover",
                      "sf_disable", "sf_erase"):
        render_template("%s/%s.yml" % (ansible_root, playbooks),
                        "%s/%s.yml.j2" % (templates, playbooks),
                        arch)

    # Generate server spec hosts file
    if not os.path.isdir("/etc/serverspec"):
        os.mkdir("/etc/serverspec")
    render_template("/etc/serverspec/hosts.yaml",
                    "%s/serverspec.yml.j2" % templates,
                    arch)

    # Generate /etc/hosts file
    render_template("/etc/hosts",
                    "%s/etc-hosts.j2" % templates,
                    arch)
