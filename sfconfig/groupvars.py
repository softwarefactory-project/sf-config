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

import uuid

from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


def get_sf_version():
    try:
        return open("/etc/sf-release").read().strip()
    except IOError:
        return "master"


def get_previous_version():
    try:
        return open("/var/lib/software-factory/.version").read().strip()
    except IOError:
        return "2.5.0"


def generate(arch, sfmain, args, components):
    """ This function 'glue' all roles and convert sfconfig.yaml """
    secrets = yaml_load("%s/secrets.yaml" % args.lib)

    # Cleanup obsolete secrets
    for unused in ("mumble_ice_secret", ):
        if unused in secrets:
            del secrets[unused]

    # Generate all variable when the value is CHANGE_ME and collect defaults
    defaults = {}
    for role in arch["roles"]:
        role_vars = yaml_load("%s/ansible/roles/sf-%s/defaults/main.yml" % (
                              args.share, role))
        defaults.update(role_vars)
        for key, value in role_vars.items():
            if str(value).strip().replace('"', '') == 'CHANGE_ME':
                if key not in secrets:
                    secrets[key] = str(uuid.uuid4())

    # Generate dynamic role variable in the glue dictionary
    glue = {'sf_tasks_dir': "%s/ansible/tasks" % args.share,
            'sf_templates_dir': "%s/templates" % args.share,
            'sf_playbooks_dir': "%s" % args.ansible_root}

    # Set all parameters as components member to simplify configure() call
    for component in components.values():
        component.args = args
        component.glue = glue
        component.secrets = secrets
        component.sfmain = sfmain
        component.arch = arch
        component.defaults = defaults

    # Set default glue
    glue["gateway_url"] = "https://%s" % sfmain["fqdn"]
    glue["sf_version"] = get_sf_version()
    glue["sf_previous_version"] = get_previous_version()

    if sfmain["debug"]:
        for service in ("managesf", "zuul", "nodepool"):
            glue["%s_loglevel" % service] = "DEBUG"
            glue["%s_root_loglevel" % service] = "INFO"

    # Prepare components
    for host in arch["inventory"]:
        for role in arch["roles"]:
            # Set component_host variable by default
            glue["%s_host" % role.replace('-', '_')] = host["hostname"]
            if role not in components:
                continue
            components[role].prepare()

    # Configure all components
    for host in arch["inventory"]:
        for role in arch["roles"]:
            if role not in components:
                continue
            components[role].configure()

    # Save secrets to new secrets file
    yaml_dump(secrets, open("%s/secrets.yaml" % args.lib, "w"))
    glue.update(secrets)
    return glue
