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

import os
import yaml


def loadConfig(config_path):
    # Discover all files in config_path
    paths = []
    if os.path.isdir(config_path):
        for root, dirs, files in os.walk(config_path, topdown=True):
            paths.extend([os.path.join(root, path) for path in files])
    else:
        paths.append(config_path)

    # Keeps only .yaml files
    paths = filter(lambda x: x.endswith('.yaml') or x.endswith('.yml'), paths)

    tenants = {}
    for path in paths:
        data = yaml.safe_load(open(path))
        if not data:
            continue
        # Merge document
        for tenant in data:
            if not isinstance(tenant, dict) or not tenant.get('tenant'):
                raise RuntimeError("%s: invalid tenant block: %s" % (
                    path, tenant
                ))
            tenant = tenant.get('tenant')
            if not tenant.get('name'):
                tenant["name"] = "local"
            tenant_conf = tenants.setdefault(tenant['name'], {})
            for source in tenant['source'].keys():
                source_conf = tenant_conf.setdefault(source, {})
                for project_type in tenant['source'][source]:
                    projects = source_conf.setdefault(project_type, [])
                    for project in tenant['source'][source][project_type]:
                        if project in projects:
                            raise RuntimeError("%s: define existing project %s"
                                               % (path, project))
                        projects.append(project)
    final_data = []
    for tenant, tenant_conf in tenants.items():
        final_data.append({'tenant': {'name': tenant, 'source': tenant_conf}})
    return final_data


def main(argv):
    if len(argv) != 3 and not os.path.isdir(argv[1]):
        print("usage: %s dir dest" % argv[0])
    data = loadConfig(argv[1])
    yaml.dump(data, open(argv[2], "w"), default_flow_style=False)

if __name__ == "__main__":
    import sys
    main(sys.argv)
