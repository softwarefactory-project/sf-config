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
import glob
import subprocess
import sys
import yaml

from jinja2 import FileSystemLoader
from jinja2.environment import Environment


def load_components(share="/usr/share/sf-config"):
    import inspect
    import imp
    import sfconfig.components

    components = {}

    for modpath in glob.glob("%s/ansible/roles/*/meta/sfconfig.py" % share):
        role_name = modpath.split('/')[-3][3:]
        module = imp.load_source("sfconfig.components.%s" % role_name,
                                 modpath)
        for clsmember in inspect.getmembers(module, inspect.isclass):
            if issubclass(clsmember[1], sfconfig.components.Component) and \
               clsmember[0] != "Component":
                component = clsmember[1]()
                if not getattr(component, "role", None):
                    component.role = role_name
                components[component.role] = component
    return components


def list_testinfra(share="/usr/share/sf-config"):
    testinfra = {}

    for modpath in glob.glob("%s/testinfra/test_*.py" % share):
        testinfra[modpath.split('_')[-1][:-3]] = modpath
    return testinfra


def get_default(d, key, default):
    val = d.get(key, default)
    if not val:
        val = default
    return val


def execute(argv):
    if subprocess.Popen(argv).wait():
        raise RuntimeError("Command failed: %s" % argv)


def pread(argv):
    return subprocess.Popen(argv, stdout=subprocess.PIPE).stdout.read()


def fail(msg):
    print >>sys.stderr, msg
    exit(1)


def render_template(dest, template, data):
    if os.path.exists(dest):
        current = open(dest).read()
    else:
        current = ""
    loader = FileSystemLoader(os.path.dirname(template))
    env = Environment(trim_blocks=True, loader=loader)
    template = env.get_template(os.path.basename(template))
    new = template.render(data)
    if new[-1] != "\n":
        new += "\n"
    if new != current:
        with open(dest, "w") as out:
            out.write(new)
        print("[+] Wrote %s" % dest)
        return True


def yaml_merge_load(inp):
    paths = []
    for root, dirs, files in os.walk(inp, topdown=True):
        paths.extend([os.path.join(root, path) for path in files])

    # Keeps only .yaml files
    paths = filter(lambda x: x.endswith('.yaml') or x.endswith('.yml'), paths)

    user = {}
    for path in paths:
        data = yaml.safe_load(open(path))
        if not data:
            continue
        for key, value in data.items():
            user.setdefault(key, []).extend(value)
    return user


def get_secret(name, filename):
    return yaml_load(filename)[name]


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
