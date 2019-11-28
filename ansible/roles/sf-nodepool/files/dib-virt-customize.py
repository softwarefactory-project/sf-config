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


import argparse
import subprocess
import os


# Wrapper to be called by nodepool-builder
# To call it outside of nodepool-builder to debug images
# run: dib-virt-customize -t qcow2 -o /tmp/test ./fedora-30-cloud.yaml


def main():
    # Fake dib interface
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", action='store_true', help="noop")
    parser.add_argument("-t", help="Image types")
    parser.add_argument("--checksum", action='store_true', help="noop")
    parser.add_argument("--no-tmpfs", action='store_true', help="noop")
    parser.add_argument("--qemu-img-options", help="noop")
    parser.add_argument("-o", help="Image output")
    parser.add_argument("virt_images", nargs='+', help="noop")
    args = parser.parse_args()
    cmd = ["sudo", "ansible-playbook", "-v"]

    # The first arguments is the playbook name
    if len(args.virt_images) != 1:
        print("Only one image definition is supported")
        exit(1)
    playbook = args.virt_images[0]
    playbook_path = None
    if os.path.exists(playbook):
        playbook_path = playbook
    else:
        vp = os.path.join(
            "/etc/nodepool/virt_images", playbook)
        if os.path.exists(vp):
            playbook_path = vp
    if not playbook_path:
        print("Can't find playbook %s" % playbook)
        exit(1)

    cmd.append(playbook_path)

    # Set the image output var
    cmd.extend(["-e", "image_output=%s" % args.o])

    # Look for image types
    img_types = set(args.t.split(','))
    unsupported_types = img_types.difference(set(('raw', 'qcow2')))
    if unsupported_types:
        raise RuntimeError("Unsupported type: %s" % unsupported_types)
    if "raw" in img_types:
        cmd.extend(["-e", "raw_type=True"])
    if "qcow2" in img_types:
        cmd.extend(["-e", "qcow2_type=True"])

    os.environ["ANSIBLE_ROLES_PATH"] = \
        "/etc/nodepool/virt_images/dib-virt-customize"
    # Execute the playbook
    print("Running: %s" % " ".join(cmd))
    return subprocess.Popen(cmd).wait()


if __name__ == "__main__":
    exit(main())
