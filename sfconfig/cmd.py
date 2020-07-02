#!/bin/env python3
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
#
# Generate ansible group vars based on refarch and sfconfig.yaml

import argparse
import os
import sys
import time

import sfconfig.arch
import sfconfig.groupvars
import sfconfig.inventory
import sfconfig.upgrade

import sfconfig.utils
from sfconfig.utils import execute
from sfconfig.utils import save_file
from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


bdir = '/var/lib/software-factory/backup'
saml_idp_file = '/etc/httpd/saml2/idp_metadata.xml'


def extract_backup(backup):
    if not os.path.isdir(bdir):
        os.makedirs(bdir, 0o700)
    # Extract backup file
    print("Extracting the archive %s in %s" % (backup, bdir))
    execute(["tar", "-xpf", backup, "-C", bdir])
    print("Archive extracted")


def copy_backup(backup):
    if backup != bdir:
        print("Copying the tree %s in %s" % (backup, bdir))
        execute(["rsync", "-a", "--delete",
                 "%s/" % backup.rstrip('/'), bdir])
        print("Tree copied")


def bootstrap_backup():
    # Copy software-factory conf
    execute(["rsync", "-a", "--exclude", "arch.yaml",
             "%s/install-server/etc/software-factory/" % bdir,
             "/etc/software-factory/"])
    # Copy bootstrap data
    execute(["rsync", "-a", "--exclude", "arch.yaml",
             "%s/install-server/var/lib/software-factory/" % bdir,
             "/var/lib/software-factory/"])
    print("Boostrap data prepared from the backup. Done.")


def usage(components):
    p = argparse.ArgumentParser()

    # inputs
    p.add_argument("--arch", default="/etc/software-factory/arch.yaml",
                   help="The architecture file")
    p.add_argument("--config", default="/etc/software-factory/sfconfig.yaml",
                   help="The configuration file")
    p.add_argument("--extra", default="/etc/software-factory/custom-vars.yaml",
                   help="Extra ansible variable file")
    p.add_argument("--share", default="/usr/share/sf-config",
                   help="Templates and ansible roles")

    # outputs
    p.add_argument("--ansible_root",
                   default="/var/lib/software-factory/ansible",
                   help="Generated playbook output directory")
    p.add_argument("--lib", default="/var/lib/software-factory/bootstrap-data",
                   help="Deployment secrets output directory")

    # common component options
    p.add_argument("--enable-insecure-workers", action='store_true',
                   help="Allow using hypervisor-* on the control plane")

    # tunning
    p.add_argument("--skip-apply", default=False, action='store_true',
                   help="Do not execute Ansible playbook")
    p.add_argument("--skip-test", default=False, action='store_true',
                   help="Do not execute testinfra")
    p.add_argument("--skip-populate-hosts", default=False, action='store_true',
                   help="Do not execute ssh populate hosts")
    p.add_argument("--disable-external-resources", default=False,
                   action='store_true',
                   help="Disable gerrit replication and nodepool providers")

    # TODO: switch default to False when 2.7 is released
    # (with zookeeper enabled in minimal arch)
    p.add_argument("--allinone", default=True, action='store_true',
                   help="Automatically add missing role to the first node")

    # special actions
    p.add_argument("--recover", nargs='?', const=bdir, metavar='BACKUP_PATH',
                   help="Deploy a backup")
    p.add_argument("--disable", action='store_true', help="Turn off services")
    p.add_argument("--erase", action='store_true', help="Erase data")
    p.add_argument("--upgrade", action='store_true', help="Run upgrade task")
    p.add_argument("--update", action='store_true', help="Run upgrade task")

    # Deprecated
    p.add_argument("--skip-install", default=False, action='store_true',
                   help="Do not call install tasks")
    p.add_argument("--skip-setup", default=False, action='store_true',
                   help="Do not call setup tasks")

    # Add components options
    for component in components.values():
        component.usage(p)

    # Hidden 3.4 backward compatible command line interface
    argv = sys.argv
    legacy_value, legacy_name = False, '--enable-insecure-slaves'
    if legacy_name in argv:
        argv.remove(legacy_name)
        legacy_value = True

    args = p.parse_args(argv)

    if args.upgrade:
        args.update = True

    if legacy_value:
        args.enable_insecure_workers = True

    return args


def fix_rhel_centos_name(glue):
    """Set correct names once and for all depending on the os id"""
    osid = list(
        filter(lambda x: x.startswith("id="),
               map(str.lower,
                   open("/etc/os-release").readlines()))
        )[0].split('=')[1].strip()[1:-1]
    if osid == "rhel":
        glue["openshift_client"] = "atomic-openshift-clients"
        glue["openshift_server"] = "atomic-openshift"

    else:
        glue["openshift_repo"] = "centos-release-openshift-origin311"
        glue["openshift_client"] = "origin-clients"
        glue["openshift_server"] = "origin"


def main():
    components = sfconfig.utils.load_components()
    args = usage(components)

    # Ensure environment is UTF-8
    os.environ["LC_ALL"] = "en_US.UTF-8"

    if not args.skip_apply:
        execute(["logger", "sfconfig: started %s" % sys.argv[1:]])
        print("[%s] Running sfconfig" % time.ctime())

    # Create required directories
    allyaml = "%s/group_vars/all.yaml" % args.ansible_root
    for dirname in (args.ansible_root,
                    "%s/group_vars" % args.ansible_root,
                    "%s/facts" % args.ansible_root,
                    "%s/ara" % args.ansible_root,
                    args.lib,
                    "%s/ssh_keys" % args.lib,
                    "%s/certs" % args.lib):
        if not os.path.isdir(dirname):
            os.makedirs(dirname, 0o700)

    if args.recover:
        if os.path.isfile(args.recover):
            extract_backup(args.recover)
        elif os.path.isdir(args.recover):
            copy_backup(args.recover)
        else:
            print('Backup archive or directory was not found')
            sys.exit(1)

        bootstrap_backup()

    args.sfconfig = yaml_load(args.config)
    args.sfarch = yaml_load(args.arch)
    args.secrets = yaml_load("%s/secrets.yaml" % args.lib)
    args.glue = {'sf_tasks_dir': "%s/ansible/tasks" % args.share,
                 'sf_templates_dir': "%s/templates" % args.share,
                 'sf_playbooks_dir': "%s" % args.ansible_root,
                 'logservers': [],
                 'executor_hosts': [],
                 'nodepool_hosts': [],
                 }
    if args.recover:
        args.glue['force_update_tasks'] = True
    else:
        args.glue['force_update_tasks'] = False

    # Make sure the yaml files are updated
    sfconfig.upgrade.update_sfconfig(args)
    sfconfig.upgrade.update_arch(args)
    fix_rhel_centos_name(args.glue)

    # Save arch if needed
    if args.save_arch:
        save_file(args.sfarch, args.arch)

    # Parse components options
    for component in components.values():
        component.argparse(args)

    # Prepare components
    for host in args.sfarch["inventory"]:
        # TODO: do not force $fqdn as host domain name
        if "hostname" not in host:
            host["hostname"] = "%s.%s" % (host["name"], args.sfconfig["fqdn"])

        for role in host["roles"]:
            # Set component_host variable by default
            args.glue["%s_host" % role.replace('-', '_')] = host["hostname"]
            if role not in components:
                continue
            components[role].prepare(args)

    # Process the arch and render playbooks
    sfconfig.arch.process(args)
    sfconfig.inventory.generate(args)

    # Check if fqdn should be updated
    args.glue["update_fqdn"] = False
    if os.path.isfile("/var/lib/software-factory/.version") and \
       os.path.isfile(allyaml):
        previous_args = yaml_load(allyaml)
        if args.sfconfig['fqdn'] != previous_args['fqdn']:
            args.glue["update_fqdn"] = True

    # Generate group vars
    sfconfig.groupvars.load(args)
    for host in args.sfarch["inventory"]:
        for role in host["roles"]:
            if role not in components:
                continue
            if not args.skip_setup:
                components[role].configure(args, host)

    # Set rdo_release_url as global vars to be usable by sf-base and sf-upgrade
    args.glue["rdo_release_url"] = args.defaults["rdo_release_url"]

    # Save config if needed
    if args.save_sfconfig:
        save_file(args.sfconfig, args.config)

    # Generate group vars
    with open(allyaml, "w") as allvars_file:
        # Add legacy content
        args.glue.update(yaml_load(args.config))
        if os.path.isfile(args.extra):
            args.glue.update(yaml_load(args.extra))
        args.glue.update(args.sfarch)
        # 3.4 backward compatible extra vars
        legacy_name = 'enable_insecure_slaves'
        if legacy_name in args.glue:
            args.glue['enable_insecure_workers'] = args.glue[legacy_name]
        yaml_dump(args.glue, allvars_file)

    if 'show_hidden_logs' not in args.glue:
        args.glue['show_hidden_logs'] = False

    # Validate role settings
    for host in args.sfarch["inventory"]:
        for role in host["roles"]:
            if role not in components:
                continue
            components[role].validate(args, host)

    sfconfig.inventory.run(args)

    if not args.skip_apply:
        execute(["logger", "sfconfig.py: ended"])
        if not args.disable or not args.erase:
            print("""%s: SUCCESS

Access dashboard: https://%s
Login with admin user, get the admin password by running:
  awk '/admin_password/ {print $2}' /etc/software-factory/sfconfig.yaml

""" % (args.sfconfig['fqdn'], args.sfconfig['fqdn']))

    if (not args.sfconfig['authentication']['SAML2']['disabled'] and
       not os.path.isfile(saml_idp_file)):
        print("""
Service Provider metadata is available at /etc/httpd/saml2/mellon_metadata.xml
Once you have the Identity Provider metadata, run:
  sfconfig --set-idp-metadata <path/to/metadata.xml>

""")

    try:
        notification = open(
            "/var/lib/software-factory/ansible/notification.txt").read()
        if notification:
            print(notification)
    except IOError:
        pass


if __name__ == "__main__":
    main()
