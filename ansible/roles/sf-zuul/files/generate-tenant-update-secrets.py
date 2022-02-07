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
#

from __future__ import print_function

import json
import os
import sys
import time
import subprocess
import configparser

from six.moves import urllib

ssh_key = "/var/lib/zuul/.ssh/zuul_worker_rsa"

gateway = sys.argv[1]
default_tenant_name = sys.argv[2]

updated_keys = []

try:
    req = urllib.request.urlopen(gateway + "/v2/resources")
    data = json.loads(req.read().decode('utf-8'))
    tenants = data.get("resources", {}).get("tenants", {})
    connections = data.get("resources", {}).get("connections", {})
except Exception:
    print("Couldn't connected to managesf")
    raise

# First find the local managesf url using the local tenant
local_url = None
for tenant, inf in tenants.items():
    if tenant == default_tenant_name:
        local_url = inf["url"]
if local_url is None:
    raise RuntimeError("Couldn't find %s url in %s" % (
        default_tenant_name, str(tenants.items())))


def run_cmd(cmd):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    p.wait()
    return p


def zuul_encrypt(private_key_file):
    import zuul.lib.encryption
    pub_key = zuul.lib.encryption.deserialize_rsa_keypair(
        open(private_key_file, "rb").read(),
        password=get_keystore_password())[1]
    pub_file = "/var/lib/zuul/tenant-secrets/%s.pub" % (
        private_key_file.replace('/', ':'))
    with open(pub_file, "wb") as pub:
        pub.write(
            zuul.lib.encryption.serialize_rsa_public_key(pub_key))
    p = run_cmd(
        ["/var/lib/zuul/scripts/zuul-encrypt-secret.py",
         pub_file, "ssh_private_key", "--infile", ssh_key])
    return p.stdout.read().decode('utf-8')


def get_keystore_password():
    config = configparser.ConfigParser()
    config.read("/etc/zuul/zuul.conf")
    return config.get("keystore", "password").encode()


def wait_for_private_key(conn_name, repo_name):
    dump_path = "/var/lib/zuul/keys-dump"
    os.makedirs(os.path.dirname(dump_path), exist_ok=True)

    def get_key_from_dump():
        data = json.loads(open(dump_path).read())
        zk_path = "/keystorage/%s/config/%s/secrets" % (conn_name, repo_name)
        secret_path = "/var/lib/zuul/keys/secrets/project"
        private_key_data_path = "%s/%s/%s/0.pem" % (
            secret_path, conn_name, repo_name)
        os.makedirs(os.path.dirname(private_key_data_path), exist_ok=True)
        keys = data.get('keys', {}).get(zk_path, {}).get("keys", [])
        if keys:
            # The data struct is a list so it assumes multiple key may exists
            # but no clue about when multiple keys may exists. So by default
            # get the first one.
            private_key_data = keys[0]["private_key"]
            open(private_key_data_path, "w").write(private_key_data)
            return private_key_data_path

    def dump_keys():
        run_cmd(["zuul", "export-keys", dump_path])

    # Will wait for 20 minutes
    for _ in range(40):
        dump_keys()
        private_key = get_key_from_dump()
        if private_key:
            return private_key
        time.sleep(30)
    raise RuntimeError(
        "Maximum retries trying to get private key for %s/%s" % (
            conn_name, repo_name))


for tenant, inf in tenants.items():
    if inf["url"] == local_url:
        # This is a local tenant, no need for tenant-update job
        continue

    tenant_secret_path = "/var/lib/zuul/tenant-secrets/" \
        "tenant-update_%s_secret.yaml" % tenant
    os.makedirs(os.path.dirname(tenant_secret_path), exist_ok=True)

    if (
            os.path.exists(tenant_secret_path) and
            "pkcs" in open(tenant_secret_path).read()):
        continue

    print("Generating secret for tenant %s" % tenant)

    req = urllib.request.urlopen(inf["url"] + "/v2/resources")
    data = json.loads(req.read().decode('utf-8'))
    tenant_config = data

    tenant_config_connection = inf["default-connection"]

    tenant_config_name = tenant_config["config-repo"][len(
        connections[tenant_config_connection]["base-url"]):].lstrip('/')

    print("Looking for %s key on connection %s in Zookeeper" % (
        tenant_config_name, tenant_config_connection))
    private_key_file = wait_for_private_key(
        tenant_config_connection, tenant_config_name)

    tenant_config_secret = zuul_encrypt(private_key_file)
    open(tenant_secret_path, "w").write(tenant_config_secret)
    updated_keys.append(tenant_secret_path)

for updated_key in updated_keys:
    print(updated_key)
