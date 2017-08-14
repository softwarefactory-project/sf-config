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


def load_components():
    import pkgutil
    import inspect
    import importlib
    import sfconfig.components

    components = {}

    for importer, modname, ispkg in pkgutil.iter_modules(
            sfconfig.components.__path__, "sfconfig.components."):
        module = importlib.import_module(modname)
        for clsmember in inspect.getmembers(module, inspect.isclass):
            if getattr(clsmember[1], "role", None):
                components[clsmember[1].role] = clsmember[1]()
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
