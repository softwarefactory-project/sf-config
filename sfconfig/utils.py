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
import subprocess
import sys
import yaml

from jinja2 import FileSystemLoader
from jinja2.environment import Environment


def fail(msg):
    print >>sys.stderr, msg
    exit(1)


def yaml_load(filename):
    try:
        return yaml.safe_load(open(filename))
    except IOError:
        return {}


def yaml_dump(content, fileobj):
    yaml.dump(content, fileobj, default_flow_style=False)


def save_file(content, filename):
    os.rename(filename, "%s.orig" % filename)
    yaml_dump(content, open(filename, "w"))
    print("Updated %s (old version saved to %s)" % (filename,
                                                    "%s.orig" % filename))


def execute(argv):
    if subprocess.Popen(argv).wait():
        raise RuntimeError("Command failed: %s" % argv)


def pread(argv):
    return subprocess.Popen(argv, stdout=subprocess.PIPE).stdout.read()


def render_template(dest, template, data):
    with open(dest, "w") as out:
        loader = FileSystemLoader(os.path.dirname(template))
        env = Environment(trim_blocks=True, loader=loader)
        template = env.get_template(os.path.basename(template))
        out.write("%s\n" % template.render(data))
    print("[+] Created %s" % dest)


def get_or_generate_ssh_key(args, name):
    priv = "%s/ssh_keys/%s" % (args.lib, name)
    pub = "%s/ssh_keys/%s.pub" % (args.lib, name)

    if not os.path.isfile(priv):
        execute(["ssh-keygen", "-t", "rsa", "-N", "", "-f", priv, "-q"])
    return {
        name: open(priv).read(),
        "%s_pub" % name: open(pub).read(),
    }
