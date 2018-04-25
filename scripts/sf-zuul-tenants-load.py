#!/bin/env python
# Copyright (C) 2018 Red Hat
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
import sys
import git
import yaml
import requests
import configparser

CONFIG_FILE = '/tmp/zuul-tenants-load.ini'


def read_config(path):
    config = configparser.ConfigParser()
    config.read(path)
    url = config.get('default', 'url')
    ssl_verify = config.get('default', 'ssl_verify')
    git_store = config.get('default', 'git_store')
    return url, ssl_verify, git_store


def get_tenants(url, verify_ssl):
    ret = requests.get(url, verify=bool(int(verify_ssl)))
    tenants = ret.json()['resources']['tenants']
    return tenants


def fetch_git_repo(tenant, url, store, ssl_verify):
    tenant_config_project_path = os.path.join(
        store, tenant, os.path.basename(url))
    if not os.path.isdir(tenant_config_project_path):
        os.makedirs(tenant_config_project_path)
    if not os.path.isdir(os.path.join(tenant_config_project_path, '.git')):
        # Clone this is the first time
        git.Repo.clone_from(
            url, tenant_config_project_path, branch='master',
            depth=1, config='http.sslVerify=%s' % bool(int(ssl_verify)))
    else:
        # Refresh the repository
        repo = git.Repo(tenant_config_project_path)
        repo.remotes.origin.pull()
    return tenant_config_project_path


def discover_yaml_files(tenants_dir):
    # Discover all files in config_path
    paths = []
    for root, dirs, files in os.walk(tenants_dir, topdown=True):
        paths.extend([os.path.join(root, path) for path in files])
    # Keeps only .yaml files
    paths = filter(lambda x: x.endswith('.yaml') or x.endswith('.yml'), paths)
    return paths


def merge_tenants_from_files(tenants, tenants_conf_files):
    for path in tenants_conf_files:
        data = yaml.safe_load(open(path))
        if not data:
            continue
        for tenant in data:
            merge_tenant_from_data(tenants, tenant, path)


def merge_tenant_from_data(tenants, tenant, path):
    # Merge document
    if not isinstance(tenant, dict) or not tenant.get('tenant'):
        raise RuntimeError("%s: invalid tenant block: %s" % (
            path, tenant
            ))
    tenant = tenant.get('tenant')
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


def final_tenant_merge(tenants):
    final_data = []
    for tenant, tenant_conf in tenants.items():
        final_data.append({'tenant': {'name': tenant, 'source': tenant_conf}})
    return final_data


def main():
    url, ssl_verify, git_store = read_config(CONFIG_FILE)
    _tenants = get_tenants(url, ssl_verify)
    tenants = {}
    for tenant, data in _tenants.items():
        path = fetch_git_repo(
            tenant, data['config-project'], git_store, ssl_verify)
        tenants_dir = os.path.join(path, 'zuul')
        if not os.path.isdir(tenants_dir):
            continue
        tenants_conf_files = discover_yaml_files(tenants_dir)
        print tenants_conf_files
        tenants = merge_tenants_from_files(tenants, tenants_conf_files)
    final_yaml = final_tenant_merge(tenants)
    print(final_yaml)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("Unexpected error running %s" % " ".join(sys.argv))
        raise
