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

import argparse
import os
import shutil
import time

from sfconfig.arch import load_arch
from sfconfig.arch import generate_inventory_and_playbooks

from sfconfig.roles import generate_role_vars

from sfconfig.upgrade import update_sfconfig
from sfconfig.upgrade import clean_arch

from sfconfig.utils import execute
from sfconfig.utils import save_file
from sfconfig.utils import yaml_load
from sfconfig.utils import yaml_dump
from sfconfig.utils import pread


def extract_backup(backup_file):
    bdir = "/var/lib/software-factory/backup"
    if os.path.isfile("%s/.recovered" % bdir):
        return
    os.makedirs(bdir, 0o700)
    # Extract backup file
    execute(["tar", "-xpf", backup_file, "-C", bdir])
    # Install sfconfig and arch in place
    shutil.copy("%s/install-server/etc/software-factory/sfconfig.yaml" % bdir,
                "/etc/software-factory/sfconfig.yaml")
    shutil.copy("%s/install-server/etc/software-factory/arch-backup.yaml" %
                bdir,
                "/etc/software-factory/arch.yaml")
    # Copy bootstrap data
    execute(["rsync", "-a",
             "%s/install-server/var/lib/software-factory/" % bdir,
             "/var/lib/software-factory/"])
    open("%s/.recovered" % bdir, "w").close()


def usage():
    p = argparse.ArgumentParser()
    # inputs
    p.add_argument("--arch", default="/etc/software-factory/arch.yaml",
                   help="The architecture file")
    p.add_argument("--sfconfig", default="/etc/software-factory/sfconfig.yaml",
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
    # tunning
    p.add_argument("--skip-apply", default=False, action='store_true',
                   help="Do not execute Ansible playbook")
    # special actions
    p.add_argument("--recover", help="Deploy a backup file")
    p.add_argument("--disable", action='store_true', help="Turn off services")
    p.add_argument("--erase", action='store_true', help="Erase data")
    p.add_argument("--upgrade", action='store_true', help="Run upgrade task")

    # Deprecated
    p.add_argument("--skip-install", default=False, action='store_true',
                   help="Do not call install tasks")
    p.add_argument("--skip-setup", default=False, action='store_true',
                   help="Do not call setup tasks")
    return p.parse_args()


def main():
    args = usage()

    if args.skip_apply:
        args.skip_install = True
        args.skip_setup = True

    if not args.skip_apply:
        execute(["logger", "sfconfig.py: started"])
        print("[%s] Running sfconfig.py" % time.ctime())

    # Create required directories
    allyaml = "%s/group_vars/all.yaml" % args.ansible_root
    for dirname in (args.ansible_root,
                    "%s/group_vars" % args.ansible_root,
                    "%s/facts" % args.ansible_root,
                    args.lib,
                    "%s/ssh_keys" % args.lib,
                    "%s/certs" % args.lib):
        if not os.path.isdir(dirname):
            os.makedirs(dirname, 0o700)
    if os.path.islink(allyaml):
        # Remove previously created link to sfconfig.yaml
        os.unlink(allyaml)

    if args.recover and os.path.isfile(args.recover):
        extract_backup(args.recover)

    # Make sure the yaml files are updated
    sfconf = yaml_load(args.sfconfig)
    sfarch = yaml_load(args.arch)
    if update_sfconfig(sfconf):
        save_file(sfconf, args.sfconfig)
    if clean_arch(sfarch):
        save_file(sfarch, args.arch)

    if args.recover and len(sfarch["inventory"]) > 1:
        print("Make sure ip addresses in %s are correct" % args.arch)
        raw_input("Press enter to continue")

    # Process the arch file and render playbooks
    local_ip = pread(["ip", "route", "get", "8.8.8.8"]).split()[6]
    arch = load_arch(args.arch, sfconf['fqdn'], local_ip)
    generate_inventory_and_playbooks(arch, args.ansible_root, args.share)

    # Generate group vars
    with open(allyaml, "w") as allvars_file:
        group_vars = generate_role_vars(arch, sfconf, args)
        # Add legacy content
        group_vars.update(yaml_load(args.sfconfig))
        if os.path.isfile(args.extra):
            group_vars.update(yaml_load(args.extra))
        group_vars.update(arch)
        yaml_dump(group_vars, allvars_file)

    print("[+] %s written!" % allyaml)
    os.environ["ANSIBLE_CONFIG"] = "/usr/share/sf-config/ansible/ansible.cfg"
    if args.disable:
        return execute(["ansible-playbook",
                        "/var/lib/software-factory/ansible/sf_disable.yml"])
    if args.erase:
        return execute(["ansible-playbook",
                        "/var/lib/software-factory/ansible/sf_erase.yml"])
    if not args.skip_apply and args.recover:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_recover.yml"])
    if not args.skip_apply and args.upgrade:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_upgrade.yml"])
    if not args.skip_install:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_install.yml"])
    if not args.skip_setup:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_setup.yml"])
    if not args.skip_apply:
        execute([
            "ansible-playbook",
            "/var/lib/software-factory/ansible/sf_configrepo_update.yml"])
    if not args.skip_apply:
        execute([
            "ansible-playbook",
            "/var/lib/software-factory/ansible/sf_postconf.yml"])

    if not args.skip_apply:
        execute(["logger", "sfconfig.py: ended"])
        print("""%s: SUCCESS

Access dashboard: https://%s
Login with admin user, get the admin password by running:
  awk '/admin_password/ {print $2}' /etc/software-factory/sfconfig.yaml

""" % (sfconf['fqdn'], sfconf['fqdn']))


if __name__ == "__main__":
    main()
