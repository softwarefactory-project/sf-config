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

from jinja2 import FileSystemLoader
from jinja2.environment import Environment


def render_template(dest, template, data):
    with open(dest, "w") as out:
        loader = FileSystemLoader(os.path.dirname(template))
        env = Environment(trim_blocks=True, loader=loader)
        template = env.get_template(os.path.basename(template))
        out.write("%s\n" % template.render(data))
    print("[+] Created %s" % dest)


def generate(arch, ansible_root, share):
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
                        "%s_services" % role_name, []).append(
                            service_name.replace('3', ''))
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
        ensure_role_services("nodepool3", ["launcher", "builder"])
        ensure_role_services("zuul3", ["scheduler", "merger", "executor",
                                       "web"])

        # if firehose role is in the arch, install publishers where needed
        if firehose:
            if "zuul" in host["roles"] or \
               "nodepool" in host["roles"] or \
               "zuul3" in host["roles"]:
                host["rolesname"].append("sf-ochlero")
            if "gerrit" in host["roles"]:
                host["rolesname"].append("sf-germqtt")

    # Check for conflicts
    for conflict in (("nodepool3", "nodepool"), ("zuul3", "zuul")):
        for host in arch["inventory"]:
            if conflict[0] in host["roles"] and conflict[1] in host["roles"]:
                raise RuntimeError("%s: can't install both %s and %s" % (
                    host["hostname"], conflict[0], conflict[1]
                ))
    if 'hydrant' in arch["roles"] and not firehose:
        raise RuntimeError("'hydrant' role needs 'firehose'")
    if 'hydrant' in arch["roles"] and 'elasticsearch' not in arch["roles"]:
        raise RuntimeError("'hydrant' role needs 'elasticsearch'")

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
