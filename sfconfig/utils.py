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
