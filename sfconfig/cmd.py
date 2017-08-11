#!/usr/bin/python
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
import shutil
import time

import sfconfig.arch
import sfconfig.inventory
import sfconfig.upgrade

from sfconfig.utils import execute
from sfconfig.utils import pread
from sfconfig.utils import save_file
from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


bdir = '/var/lib/software-factory/backup'


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


def bootstrap_backup(use_new_arch=False):
    # Install sfconfig and arch in place
    shutil.copy("%s/install-server/etc/software-factory/sfconfig.yaml" % bdir,
                "/etc/software-factory/sfconfig.yaml")
    if not use_new_arch:
        shutil.copy("%s/install-server/etc/software-factory/arch-backup.yaml" %
                    bdir, "/etc/software-factory/arch.yaml")
    # Copy bootstrap data
    execute(["rsync", "-a",
             "%s/install-server/var/lib/software-factory/" % bdir,
             "/var/lib/software-factory/"])
    print("Boostrap data prepared from the backup. Done.")


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
    p.add_argument("--disable-external-resources", default=False,
                   action='store_true',
                   help="Disable gerrit replication and nodepool providers")
    # special actions
    p.add_argument("--recover", nargs='?', const=bdir, metavar='BACKUP_PATH',
                   help="Deploy a backup")
    p.add_argument("--use-new-arch", action='store_true',
                   help="When restoring a backup, keep the arch setup by heat")
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

    if args.recover:
        if os.path.isfile(args.recover):
            extract_backup(args.recover)
        elif os.path.isdir(args.recover):
            copy_backup(args.recover)
        else:
            print('Backup archive or directory was not found')
            sys.exit(1)

        bootstrap_backup(args.use_new_arch)

    # Make sure the yaml files are updated
    sfmain = yaml_load(args.sfconfig)
    sfarch = yaml_load(args.arch)
    if sfconfig.upgrade.update_sfconfig(sfmain, args):
        save_file(sfmain, args.sfconfig)
    if sfconfig.upgrade.update_arch(sfarch):
        save_file(sfarch, args.arch)

    if not args.use_new_arch and args.recover and len(sfarch["inventory"]) > 1:
        print("Make sure ip addresses in %s are correct" % args.arch)
        raw_input("Press enter to continue")

    # Process the arch file and render playbooks
    local_ip = pread(["ip", "route", "get", "8.8.8.8"]).split()[6]
    arch = sfconfig.arch.load(args.arch, sfmain['fqdn'], local_ip)
    sfconfig.inventory.generate(arch, args.ansible_root, args.share)

    # Generate group vars
    with open(allyaml, "w") as allvars_file:
        group_vars = sfconfig.groupvars.generate(arch, sfmain, args)
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
    if not args.skip_apply and args.upgrade:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_upgrade.yml"])
    if not args.skip_install:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_install.yml"])
    if not args.skip_apply and args.recover:
        execute(["ansible-playbook",
                 "/var/lib/software-factory/ansible/sf_recover.yml"])
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

""" % (sfmain['fqdn'], sfmain['fqdn']))


if __name__ == "__main__":
    main()
