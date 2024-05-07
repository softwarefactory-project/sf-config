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

"""SF in a podman: this is a script to buildah an all-in-one SF container.
The image uses a systemd target to start the services as if it was a
regular linux instance. The goal is to enable localhost/developper laptop
deployment for quick prototype and reproducer purpose...

A bit of usage for buildah (the builder) and podman (the runner):

buildah containers         # list the container used by buildah
buildah delete --all       # cleanup stalled build env

podman images              # list available images
podman ps -a               # list processes
podman rmi                 # delete an image
podman rm                  # delete container
podman kill -a --signal 9  # kill all the containers

# Quickly mount, hack and commit an image:
IMAGE=softwarefactoryproject/sf-allinone:latest
ctn=$(buildah from ${IMAGE}); mnt=$(buildah mount $ctn)
  buildah run $ctn yum install -y htop # ...
  vim ${mnt}/usr/share/sf-config/      # ...
buildah umount $ctn && buildah commit $ctn ${IMAGE} && buildah delete $ctn

# Try an image interactively (--rm delete after use, -it means interactive)
podman run --rm -it ${IMAGE} /bin/bash

Skopeo can be used to inspect image content and publish them:

skopeo inspect containers-storage:${podman_images_output_id}
skopeo inspect docker://docker.io/softwarefactoryproject/sf-allinone:latest
skopeo copy skopeo  copy --dest-creds username \
    containers-storage:id docker://docker.io/name
"""

import json
import logging
import os
from utils import execute, pread


class Buildah:
    log = logging.getLogger("Buildah")

    def __init__(self):
        # Use podman because of:
        # https://github.com/containers/buildah/issues/1257
        images = pread(["podman", "images", "--format", "json"])
        if images:
            self.images = json.loads(images)
        else:
            self.images = []

        self.builds = []
        self.mnt, self.container = None, None

    def image_exists(self, name):
        for image in self.images:
            if image['names'] and "localhost/%s" % name in image['names']:
                return image['id']

    def run(self, cmd):
        self.log.debug("Running %s" % cmd)
        execute(["buildah", "run", self.container, "--"] + cmd.split())

    def config(self, cmd):
        execute(["buildah", "config"] + cmd.split() + [self.container])

    def copy(self, path, content, mode=None):
        with open(os.path.join(self.mnt, path), "w") as of:
            of.write(content + "\n")
        if mode:
            os.chmod(os.path.join(self.mnt, path), mode)

    def build(self, force, arch, version):
        def get_image_name(version, arch):
            return "softwarefactoryproject/sf-%s:%s" % (
                arch, "latest" if version == "master" else version)

        # First let's build the zuul-minimal
        layer0 = get_image_name(version, "zuul-minimal")
        if force or not self.image_exists(layer0):
            self.build_arch("centos:latest", version, "zuul-minimal", layer0)
        else:
            self.log.info("Re-using existing %s layer", layer0)

        # Then let's build the minimal arch
        if arch not in ("minimal", "allinone"):
            return
        layer1 = get_image_name(version, "minimal")
        if force or not self.image_exists(layer1):
            self.build_arch(layer0, version, "minimal", layer1)
        else:
            self.log.info("Re-using existing %s layer", layer1)

        # Then let's build the allinone arch
        if arch != "allinone":
            return
        layer2 = get_image_name(version, arch)
        if force or not self.image_exists(layer2):
            self.build_arch(layer1, version, "allinone", layer2)
        else:
            self.log.info("Re-using existing %s layer", layer2)

    def build_arch(self, parent_layer, version, arch, output_name):
        self.log.info("Building the %s layer" % output_name)
        self.container = pread(["buildah", "from", parent_layer]).strip()
        if arch == "zuul-minimal":
            self.mnt = pread(["buildah", "mount", self.container]).strip()
            self.system(version)
            if version == "master":
                self.local_fixes()
            self.mitogen()
            self.sfconfig_install("zuul-minimal")
            self.sfconfig_systemd()
        else:
            self.sfconfig_install(arch)
        self.finalize(arch)
        self.cleanup()
        self.kill(tag_name=output_name)

    def system(self, version):
        self.log.info("Installing ansible")
        self.run("yum install -y ansible")

    def local_fixes(self):
        try:
            gitroot = pread(["git", "rev-parse", "--show-toplevel"]).strip()
            self.log.info("Installing local git repository content")
            execute([
                "rsync", "-a", os.path.join(gitroot, "ansible/"),
                os.path.join(self.mnt, "usr/share/sf-config/ansible/")])
            execute([
                "rsync", "-a", os.path.join(gitroot, "templates/"),
                os.path.join(self.mnt, "usr/share/sf-config/templates/")])
            execute([
                "rsync", "-a", os.path.join(gitroot, "sfconfig/"),
                os.path.join(self.mnt, "usr/lib/python2.7/site-packages/"
                             "sfconfig/")])
        except RuntimeError:
            pass

    def sfconfig_install(self, arch):
        self.log.info("Running sfconfig install playbook")
        self.run("cp /usr/share/sf-config/refarch/%s.yaml "
                 "/etc/software-factory/arch.yaml" % arch)
        self.run("sfconfig --skip-setup")

    def sfconfig_systemd(self):
        self.log.info("Installing systemd target")
        # Install custom systemd target and service to trigger sfconfig on boot
        self.copy("etc/systemd/system/sf.target", """[Unit]
Description=Software Factory boot target
Requires=basic.target network.target network-online.target
Wants=sfconfig.service
After=basic.target""")
        self.run("ln -sf /etc/systemd/system/sf.target "
                 "/etc/systemd/system/default.target")
        self.copy("lib/systemd/system/sfconfig.service", """[Unit]
Description=sfconfig configuration script
Requires=dbus.service sshd.service

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
hostname managesf.sfpodman.local
sed -e 's/sftests.com/sfpodman.local/' -i /etc/software-factory/sfconfig.yaml
cat <<EOF> /etc/software-factory/custom-vars.yaml
provision_demo: true
gateway_force_ssl_redirection: false
EOF

# enable exec in /tmp (TODO: figure out what set it to noexec...)
mount -o remount,exec /tmp

# setup services
sfconfig --skip-install
journalctl -f &
exec bash
""", mode=0o755)

    def mitogen(self):
        self.log.info("Enabling mitogen")
        # Let's give mitogen a try...
        self.run("pip3 install mitogen==0.2.3")
        pypath = "/usr/lib/python3.6/site-packages/"
        execute(["sed",
                 "-e", "2istrategy = mitogen_linear",
                 "-e", "2istrategy_plugins = %s" % os.path.join(
                     pypath, "ansible_mitogen/plugins/strategy/"),
                 "-i", os.path.join(
                     self.mnt,
                     "usr/share/sf-config/ansible/ansible.cfg")])
        # Unfortunately this needs a couple of hacks...
        pymnt = os.path.join(self.mnt, pypath[1:])
        execute(["sed", "-e", "s/os.chdir/pass # os.chdir/", "-i",
                 os.path.join(pymnt, "ansible_mitogen/runner.py")])
        execute(["sed", "-e", "s#os.chdir(prev_dir)#"
                 "os.chdir(prev_dir if os.path.exists(prev_dir) else '/')#",
                 "-i", os.path.join(pymnt, "ansible/module_utils/basic.py")])

    def finalize(self, arch):
        self.config("--cmd /sbin/init")
        if arch == "zuul-minimal":
            for port in ("80", "443"):
                self.config("--port %s" % port)
        else:
            self.config("--port 29418")
        self.config("--created-by Software-Factory-CI")
        self.config("--author release@softwarefactory-project.io")

    def cleanup(self):
        self.run("yum clean all")

    def kill(self, tag_name=None):
        if self.mnt:
            try:
                self.log.info("Umounting the container %s", self.container)
                execute(["buildah", "umount", self.container])
                self.mnt = None
            except Exception:
                self.log.exception("Umount failed")
        if tag_name:
            self.log.info("Commiting %s", tag_name)
            execute(["buildah", "commit", self.container, tag_name])
            self.builds.append(tag_name)
        try:
            self.log.info("Deleting the container %s", self.container)
            execute(["buildah", "delete", self.container])
        except Exception:
            self.log.exception("Delete failed")
        self.container = None


if __name__ == "__main__":
    import argparse

    if os.getuid() != 0:
        print("Only root can do that")
        exit(1)
    parser = argparse.ArgumentParser(description="Deploy sf in podman")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debugging trace.")
    parser.add_argument("--force", action="store_true",
                        help="Force rebuild.")
    parser.add_argument("--arch", default="allinone",
                        help="The sfconfig architecture.")
    parser.add_argument("--version", default="master",
                        help="The image version.")
    args = parser.parse_args()
    logging.basicConfig(
        format='\033[1;35m'
        '%(asctime)s %(levelname)-5.5s %(name)s - %(message)s\033[1;0m',
        level=logging.DEBUG if args.debug else logging.INFO)

    buildah = Buildah()
    try:
        buildah.build(args.force, args.arch, args.version)
    except Exception:
        if not args.debug and buildah.container:
            buildah.kill()
        else:
            print("Buildah context isn't removed")
            raise
    print("Publish the image using this command:")
    for image in buildah.builds:
        print("podman push localhost/%s docker://docker.io/%s" % (
            image, image))
