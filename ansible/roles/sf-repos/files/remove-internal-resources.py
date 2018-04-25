#!/usr/bin/python

""" Remove resources from common files that are now managed in _internal.yaml
"""

import sys
import os
import yaml


try:
    resources_dir = sys.argv[1]
    assert os.path.isdir(resources_dir)
except Exception:
    print("usage: %s <resources_dir>" % sys.argv[0])
    exit(1)

# Discover all files
paths = []
for root, dirs, files in os.walk(resources_dir, topdown=True):
    paths.extend([os.path.join(root, path) for path in files])

# Search and remove managed resources
for path in paths:
    data = yaml.safe_load(open(path))
    dirty = False
    if not data:
        continue

    def get_keys(rtype):
        return list(data.get('resources', {}).get(rtype, {}).keys())

    for project in get_keys('projects'):
        if project == 'internal':
            del data['resources']['projects'][project]
            dirty = True
    for repo in get_keys('repos'):
        if repo in ('config', 'sf-jobs', 'zuul-jobs'):
            del data['resources']['repos'][repo]
            dirty = True
    for acl in get_keys('acls'):
        if acl == "config-acl":
            del data['resources']['acls'][acl]
            dirty = True
    if dirty:
        for rtype in ('projects', 'repos', 'acls'):
            if not data.get('resources', {}).get(rtype):
                try:
                    del data['resources'][rtype]
                except KeyError:
                    pass
        print("Updating %s" % path)
        yaml.dump(data, open(path, "w"), default_flow_style=False)
