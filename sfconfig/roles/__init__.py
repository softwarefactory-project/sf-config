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

import uuid

from sfconfig.utils import get_or_generate_ssh_key
from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load

from sfconfig.roles import cauth
from sfconfig.roles import etherpad
from sfconfig.roles import gateway
from sfconfig.roles import gerrit
from sfconfig.roles import grafana
from sfconfig.roles import jenkins
from sfconfig.roles import lodgeit
from sfconfig.roles import logserver
from sfconfig.roles import managesf
from sfconfig.roles import murmur
from sfconfig.roles import nodepool
from sfconfig.roles import pages
from sfconfig.roles import storyboard
from sfconfig.roles import zuul

ROLES = {
    "cauth": cauth.configure,
    "etherpad": etherpad.configure,
    "gateway": gateway.configure,
    "gerrit": gerrit.configure,
    "grafana": grafana.configure,
    "jenkins": jenkins.configure,
    "lodgeit": lodgeit.configure,
    "logserver": logserver.configure,
    "managesf": managesf.configure,
    "murmur": murmur.configure,
    "nodepool-launcher": nodepool.configure_launcher,
    "pages": pages.configure,
    "storyboard": storyboard.configure,
    'zuul-server': zuul.configure_server,
    'zuul-launcher': zuul.configure_launcher,
}


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


def generate_role_vars(arch, sfconf, args):
    """ This function 'glue' all roles and convert sfconfig.yaml """
    secrets = yaml_load("%s/secrets.yaml" % args.lib)

    # Cleanup obsolete secrets
    for unused in ("mumble_ice_secret", ):
        if unused in secrets:
            del secrets[unused]

    # Generate all variable when the value is CHANGE_ME
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
    glue = {'mysql_databases': {},
            'sf_tasks_dir': "%s/ansible/tasks" % args.share,
            'sf_templates_dir': "%s/templates" % args.share,
            'sf_playbooks_dir': "%s" % args.ansible_root,
            'jobs_zmq_publishers': [],
            'loguser_authorized_keys': [],
            'pagesuser_authorized_keys': [],
            'logservers': [],
            }

    glue["sf_version"] = get_sf_version()
    glue["sf_previous_version"] = get_previous_version()
    if "koji_host" in sfconf["network"] and sfconf["network"]["koji_host"]:
        glue["koji_host"] = sfconf["network"]["koji_host"]

    glue.update(get_or_generate_ssh_key(args, "service_rsa"))

    if sfconf["debug"]:
        for service in ("managesf", "zuul", "nodepool"):
            glue["%s_loglevel" % service] = "DEBUG"
            glue["%s_root_loglevel" % service] = "INFO"

    for host in arch["inventory"]:
        for role in host["roles"]:
            host_var = "%s_host" % role.replace('-', '_')
            if host_var not in glue:
                glue[host_var] = host["hostname"]
            if role in ROLES:
                ROLES[role](args, host, sfconf, arch, glue, secrets, defaults)

    # Save secrets to new secrets file
    yaml_dump(secrets, open("%s/secrets.yaml" % args.lib, "w"))
    glue.update(secrets)
    return glue
