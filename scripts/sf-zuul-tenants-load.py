#!/bin/env python3
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

# TODO(fbo):
# - more unittest
# - missing repositories support for gerrit and github
# - better error handling


import os
import sys
import git
import yaml
import requests
import configparser

import unittest


CONFIG_FILE = '/tmp/zuul-tenants-load.ini'


class ZuulTenantsLoad(object):

    def read_config(self, path):
        config = configparser.ConfigParser()
        config.read(path)
        url = config.get('default', 'url')
        ssl_verify = config.get('default', 'ssl_verify')
        git_store = config.get('default', 'git_store')
        return url, ssl_verify, git_store

    def get_tenants(self, url, verify_ssl):
        ret = requests.get(url, verify=bool(int(verify_ssl)))
        tenants = ret.json()['resources']['tenants']
        return tenants

    def fetch_git_repo(self, tenant, url, store, ssl_verify):
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

    def discover_yaml_files(self, tenants_dir):
        # Discover all files in config_path
        paths = []
        for root, dirs, files in os.walk(tenants_dir, topdown=True):
            paths.extend([os.path.join(root, path) for path in files])
            # Keeps only .yaml files
        paths = filter(
            lambda x: x.endswith('.yaml') or x.endswith('.yml'), paths)
        return paths

    def merge_tenants_from_files(
            self, tenants, tenants_conf_files, tenant_name):
        for path in tenants_conf_files:
            data = yaml.safe_load(open(path))
            if not data:
                continue
            for tenant in data:
                self.merge_tenant_from_data(
                    tenants, tenant, path, tenant_name)

    def merge_source(self, tenant_conf, sources, path, tenant_name):
        tenant_sources = tenant_conf.setdefault("source", {})
        for source in sources.keys():
            source_conf = tenant_sources.setdefault(source, {})
            for project_type in sources[source]:
                projects = source_conf.setdefault(project_type, [])
                for project in sources[source][project_type]:
                    if project in projects:
                        raise RuntimeError(
                            "%s: define existing project %s for tenant %s"
                            % (path, project, tenant_name))
                    projects.append(project)

    def merge_tenant_from_data(self, tenants, tenant, path, tenant_name):
        # Merge document
        if not isinstance(tenant, dict) or not tenant.get('tenant'):
            raise RuntimeError("%s: invalid tenant block: %s" % (
                path, tenant
            ))
        tenant = tenant.get('tenant')
        if tenant['name'] != tenant_name:
            return
        tenant_conf = tenants.setdefault(
            tenant['name'], {})
        for name, value in tenant.items():
            if name == "source":
                # Merge source lists
                self.merge_source(tenant_conf, value, path, tenant_name)
            elif name != "name":
                # Set tenant option
                if name in tenant_conf:
                    raise RuntimeError(
                        "%s: define multiple %s for tenant %s" % (
                            path, tenant["name"], name))
                tenant_conf[name] = value

    def final_tenant_merge(self, tenants):
        final_data = []
        for tenant, tenant_conf in tenants.items():
            data = {'tenant': {'name': tenant}}
            data['tenant'].update(tenant_conf)
            final_data.append(data)
        return final_data

    def start(self):
        url, ssl_verify, git_store = self.read_config(CONFIG_FILE)
        _tenants = self.get_tenants(url, ssl_verify)
        tenants = {}
        for tenant_name, data in _tenants.items():
            path = self.fetch_git_repo(
                tenant_name, data['config-project'], git_store, ssl_verify)
            tenants_dir = os.path.join(path, 'zuul')
            if not os.path.isdir(tenants_dir):
                continue
            tenants_conf_files = self.discover_yaml_files(tenants_dir)
            self.merge_tenants_from_files(
                tenants, tenants_conf_files, tenant_name)
            # repos = self.list_org_repositories(
            #     tenant_name, data['config-project'])
            # missing_repos = self.find_missing_repos(
            #    tenants, tenant_name, repos)
            # self.merge_missing_repos(
            #    tenants, tenant_name, missing_repos)
        final_yaml = self.final_tenant_merge(tenants)
        print(yaml.dump(final_yaml))
        return 0


class TenantsLoadTests(unittest.TestCase):

    def test_merge_tenant_case_1(self):
        ztl = ZuulTenantsLoad()
        tenants_data = """
        - tenant:
            name: local
            source:
              gerrit:
                config-projects:
                  - common-config
        - tenant:
            name: local
            max-nodes-per-job: 5
            source:
              gerrit:
                untrusted-projects:
                  - repo1
                  - repo2
        """
        final_tenants = {}
        tenants = yaml.load(tenants_data)
        for tenant in tenants:
            ztl.merge_tenant_from_data(
                final_tenants, tenant, '/data', 'local')
        final_tenants = ztl.final_tenant_merge(final_tenants)
        expected = {
            'tenant': {
                'name': 'local',
                'max-nodes-per-job': 5,
                'source': {
                    'gerrit': {
                        'config-projects': ['common-config'],
                        'untrusted-projects': ['repo1', 'repo2']
                        }
                    }
                }
            }
        self.assertDictEqual(final_tenants[0], expected)
        self.assertEqual(len(final_tenants), 1)

    def test_merge_tenant_case_2(self):
        ztl = ZuulTenantsLoad()
        tenant_data = """
        - tenant:
            name: local
            source:
              gerrit:
                config-projects:
                  - config
        - tenant:
            name: local
            source:
              gerrit:
                config-projects:
                  - config
        """
        final_tenants = {}
        tenants = yaml.load(tenant_data)
        ztl.merge_tenant_from_data(final_tenants, tenants[0], '/data', 'local')
        with self.assertRaises(RuntimeError) as exc:
            ztl.merge_tenant_from_data(
                final_tenants, tenants[1], '/data', 'local')
            self.assertEqual(
                str(exc),
                '/data: define existing project config for tenant local')

    def test_merge_tenant_case_3(self):
        ztl = ZuulTenantsLoad()
        tenant_data_1 = """
        - tenant:
            name: local
            source:
              gerrit:
                config-projects:
                  - config
        """
        tenant_data_2 = """
        - tenant:
            name: ansible-network
            max-nodes-per-job: 5
            source:
              gerrit:
                config-projects:
                  - config
              github:
                untrusted-projects:
                  - repo1
                  - repo2
        """
        final_tenants = {}
        tenant1 = yaml.load(tenant_data_1)[0]
        tenant2 = yaml.load(tenant_data_2)[0]
        ztl.merge_tenant_from_data(
            final_tenants, tenant1, '/t1', 'local')
        ztl.merge_tenant_from_data(
            final_tenants, tenant2, '/t2', 'ansible-network')
        final_tenants = ztl.final_tenant_merge(final_tenants)
        expected_tenant_ansible_network = {
            'tenant': {
                'max-nodes-per-job': 5,
                'name': 'ansible-network',
                'source': {
                    'github': {
                        'untrusted-projects': ['repo1', 'repo2']
                        },
                    'gerrit': {
                        'config-projects': ['config']
                        }
                    }
                }
            }
        expected_tenant_local = {
            'tenant': {
                'name': 'local',
                'source': {
                    'gerrit': {
                        'config-projects': ['config']
                        }
                    }
                }
            }
        self.assertDictEqual(
            [t for t in final_tenants if
             t['tenant']['name'] == 'ansible-network'][0],
            expected_tenant_ansible_network)
        self.assertDictEqual(
            [t for t in final_tenants if
             t['tenant']['name'] == 'local'][0],
            expected_tenant_local)
        self.assertEqual(len(final_tenants), 2)


if __name__ == "__main__":
    try:
        ztl = ZuulTenantsLoad()
        sys.exit(ztl.start())
    except Exception:
        print("Unexpected error running %s" % " ".join(sys.argv))
        raise
