#!/bin/env python
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

"""SF in a podman: this is a script to buildah an all-in-one SF containers.
The image uses a systemd target to start the services as if it was a
regular linux instance. The goal is to enable localhost/developper laptop
deployment for quick prototype and reproducer purpose...

A bit of usage for buildah (the builder) and podman (the runner):

buildah containers         # list the container used by buildah
buildah delete --all       # cleanup stalled build env

podman images              # list available images
podman rmi                 # delete an image
podman ps -a               # list process
podman rm                  # remove container
podman kill -a --signal 9  # kill all the containers

# Quickly mount, hack and commit an image named SF
IMAGE=docker.io/softwarefactoryproject/sf-allinone:latest
ctn=$(buildah from ${IMAGE}); mnt=$(buildah mount $ctn)
  buildah run $ctn yum install -y htop # ...
  vim ${mnt}/usr/share/sf-config/      # ...
buildah umount $ctn && buildah commit $ctn ${IMAGE} && buildah delete $ctn

# Try an image interactively (rm means delete after use, it means interactive)
podman run --rm -it ${IMAGE} /bin/bash
"""

import json
import logging
import os
from utils import execute, pread

SF_RELEASE_URL = "https://softwarefactory-project.io/repos/sf-release-3.2.rpm"
IMAGE = "docker.io/softwarefactoryproject/sf-allinone"


class Buildah:
    log = logging.getLogger("Buildah")

    def __init__(self):
        self.container = pread(["buildah", "from", "centos:latest"]).strip()
        self.mountpath = pread(["buildah", "mount", self.container]).strip()
        self.log.info(
            "container=%s scratchmnt=%s", self.container, self.mountpath)

    def delete(self, commit=None):
        try:
            self.log.info("Umounting the container")
            execute(["buildah", "umount", self.container])
        except Exception as e:
            self.log.exception("Umount failed")
        if commit:
            self.log.info("Commiting %s", self.container)
            execute(["buildah", "commit", self.container, "%s:%s" % (
                IMAGE, commit)])
        try:
            self.log.info("Deleting the container")
            execute(["buildah", "delete", self.container])
        except Exception as e:
            self.log.exception("Delete failed")
        self.container = None

    def run(self, cmd):
        self.log.debug("Running %s" % cmd)
        execute(["buildah", "run", self.container, "--"] + cmd.split())

    def config(self, cmd):
        execute(["buildah", "config"] + cmd.split() + [self.container])

    def copy(self, path, content, mode=None):
        with open(os.path.join(self.mountpath, path), "w") as of:
            of.write(content + "\n")
        if mode:
            os.chmod(os.path.join(self.mountpath, path), mode)

    def build(self, tag="latest"):
        self.system()
        self.local_fixes()
        self.sfconfig_install()
        self.sfconfig_systemd()
        self.mitogen()
        self.finalize()
        self.cleanup()
        self.delete(commit=tag)

    def system(self):
        self.log.info("Installing sfconfig and system tools")
        self.run("yum update -y")
        self.run("yum install -y %s" % SF_RELEASE_URL)
        self.run("yum install -y rh-python35-ansible sf-config")
        # Add missing package from centos:latest
        self.run("yum install -y iproute rsync git traceroute openssh openssl "
                 "openssh-server sudo crontabs")

    def local_fixes(self):
        try:
            gitroot = pread(["git", "rev-parse", "--show-toplevel"]).strip()
            self.log.info("Installing local git repository roles")
            execute([
                "rsync", "-a", os.path.join(gitroot, "ansible/"),
                os.path.join(self.mountpath, "usr/share/sf-config/ansible/")])
        except RuntimeError:
            pass

    def sfconfig_install(self):
        self.log.info("Running sfconfig install playbook")
        # Prep install playbook
        self.copy("inventory", "[managesf]\n"
                  "localhost ansible_connection=local")
        self.copy("install.yaml", """- hosts: localhost
  vars:
    role_action: 'install'
    zuul_services: ['zuul-scheduler', 'zuul-executor', 'zuul-web']
    nodepool_services: ['nodepool-launcher']
    executor_hosts: ['localhost']
    # These variables are missing defaults
    nodepool_openshift_providers: []
    nodepool_kube_file: false
  roles:
    - sf-base
    - sf-install-server
    - sf-mysql
    - sf-zookeeper
    - sf-gateway
    - sf-cauth
    - sf-managesf
    - sf-gitweb
    - sf-gerrit
    - sf-logserver
    - sf-zuul
    - sf-nodepool
    - sf-hypervisor-runc""")
        # Run install playbook
        self.run("scl enable rh-python35 -- env "
                 "ANSIBLE_ROLES_PATH=/usr/share/sf-config/ansible/roles "
                 "ansible-playbook -i /inventory -v /install.yaml "
                 "-e ansible_python_interpreter=/usr/bin/python")

    def sfconfig_systemd(self):
        self.log.info("Installing systemd target")
        # Install custom systemd target and service to trigger sfconfig on boot
        self.copy("etc/systemd/system/sf.target", """[Unit]
Description=Software Factory boot target
Requires=basic.target network.target network-online.target
Wants=sfconfig.service dbus.service sshd.service
After=basic.target""")
        self.run("ln -sf /etc/systemd/system/sf.target "
                 "/etc/systemd/system/default.target")
        self.copy("lib/systemd/system/sfconfig.service", """[Unit]
[Unit]
Description=sfconfig configuration script

[Service]
Type=simple
ExecStart=/usr/libexec/software-factory/sfinit
TimeoutSec=0
StandardOutput=tty
StandardError=tty
StandardInput=tty
TTYPath=/dev/pts/0
TTYReset=yes
TTYVHangup=yes""")

        # Install the init trampoline script
        self.copy("usr/libexec/software-factory/sfinit", """#!/bin/bash -i
# prettify env
export HOME=/root
export TERM=xterm
source /etc/profile

# fix hostname (hostnamectl doesn't work in podman)
hostname sf.podman.local
sed -e 's/sftests.com/podman.local/' -i /etc/software-factory/sfconfig.yaml
sed -e 's/name: managesf/name: sf/' -i /etc/software-factory/arch.yaml
cat <<EOF> /etc/software-factory/custom-vars.yaml
enable_insecure_slaves: true
provision_demo: true
gateway_force_ssl_redirection: false
EOF

# enable exec in /tmp (TODO: figure out what set it to noexec...)
mount -o remount,exec /tmp

# setup services
[ -f /etc/software-factory/initialized ] || \
  sfconfig --skip-install && touch /etc/software-factory/created
journalctl -f &
exec bash
""", mode=0o755)

    def mitogen(self):
        self.log.info("Enabling mitogen")
        # Let's give mitogen a try...
        self.run("scl enable rh-python35 -- pip3 install mitogen")
        pypath = "/opt/rh/rh-python35/root/lib/python3.5/site-packages/"
        execute(["sed",
                 "-e", "2istrategy = mitogen_linear",
                 "-e", "2istrategy_plugins = %s" % os.path.join(
                     pypath, "ansible_mitogen/plugins/strategy/"),
                 "-i", os.path.join(
                     self.mountpath,
                     "usr/share/sf-config/ansible/ansible.cfg")])
        # Unfortunately this needs a couple of hacks...
        pymnt = os.path.join(self.mountpath, pypath[1:])
        execute(["sed", "-e", "s/os.chdir/pass # os.chdir/", "-i",
                 os.path.join(pymnt, "ansible_mitogen/runner.py")])
        execute(["sed", "-e", "s#os.chdir(prev_dir)#"
                 "os.chdir(prev_dir if os.path.exists(prev_dir) else '/')#",
                 "-i", os.path.join(pymnt, "ansible/module_utils/basic.py")])

    def finalize(self):
        self.config("--cmd /sbin/init")
        for port in ("80", "443", "29418"):
            self.config("--port %s" % port)
        self.config("--created-by Software-Factory-CI")
        self.config("--author release@softwarefactory-project.io")

    def cleanup(self):
        self.run("yum clean all")
        for p in ("inventory", "install.retry", "install.yaml"):
            cp = os.path.join(self.mountpath, p)
            if os.path.exists(cp):
                os.unlink(cp)


class Podman:
    def __init__(self):
        self.images = json.loads(pread(
            ["podman", "images", "--format", "json"]))

    def image(self, tag="latest"):
        for image in self.images:
            if image['names'] and "%s:%s" % (IMAGE, tag) in image['names']:
                return image['id']
        return None

    def pull(self, tag="latest"):
        execute(["podman", "pull", "%s:%s" % (IMAGE, tag)])

    def create(self, tag="latest"):
        execute(["podman", "run", "--privileged", "-it",
                 "--publish-all",
                 "--name", "sf-%s.podman" % tag,
                 "-v", "/sys/fs/cgroup:/sys/fs/cgroup:ro",
                 "%s:%s" % (IMAGE, tag)])

    def start(self, tag="latest"):
        try:
            execute(["podman", "start", "-a", "sf-%s.podman" % tag])
            return True
        except RuntimeError:
            return False


if __name__ == "__main__":
    import argparse

    if os.getuid() != 0:
        print("Only root can do that")
        exit(1)
    parser = argparse.ArgumentParser(description="Deploy sf in podman")
    parser.add_argument("--build", action="store_true",
                        help="Build a local image.")
    parser.add_argument("--pull", action="store_true",
                        help="Pull the image from registry.")
    parser.add_argument("--reset", action="store_true",
                        help="Delete pod and redeploy from scratch")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debugging trace")
    parser.add_argument("--tag", default="latest",
                        help="The image version...")
    args = parser.parse_args()
    logging.basicConfig(
        format='\033[1;35m'
        '%(asctime)s %(levelname)-5.5s %(name)s - %(message)s\033[1;0m',
        level=logging.DEBUG if args.debug else logging.INFO)

    if args.build and args.pull:
        print("--build and --pull are exclusive, pick one!")
        exit(1)

    podman = Podman()
    if not podman.image(args.tag):
        if args.pull:
            podman.pull(args.tag)
        else:
            buildah = Buildah()
            try:
                buildah.build(args.tag)
            except Exception:
                if not args.debug:
                    buildah.delete()
                else:
                    print("Buildah context isn't removed")
                raise
    if not podman.start(args.tag):
        podman.create(args.tag)
