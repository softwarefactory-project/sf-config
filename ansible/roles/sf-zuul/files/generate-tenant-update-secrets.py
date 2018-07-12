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

from six.moves import urllib

ssh_key = "/var/lib/zuul/.ssh/zuul_worker_rsa"

gateway = sys.argv[1]
default_tenant_name = sys.argv[2]

updated_keys = []

try:
    req = urllib.request.urlopen(gateway + "/resources")
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


def zuul_encrypt(private_key_file, secret_file):
    import zuul.lib.encryption
    import subprocess
    pub_key = zuul.lib.encryption.deserialize_rsa_keypair(
        open(private_key_file, "rb").read())[1]
    with open("%s.pub" % private_key_file, "wb") as pub:
        pub.write(
            zuul.lib.encryption.serialize_rsa_public_key(pub_key))
    p = subprocess.Popen(
        ["/usr/share/sf-config/scripts/zuul-encrypt-secret.py", "%s.pub" %
         private_key_file, "ssh_private_key", "--infile", ssh_key],
        stdout=subprocess.PIPE)
    p.wait()
    return p.stdout.read().decode('utf-8')


for tenant, inf in tenants.items():
    if inf["url"] == local_url:
        # This is a local tenant, no need for tenant-update job
        continue

    tenant_secret_path = "/var/lib/software-factory/bootstrap-data/" \
                         "tenant-update_%s_secret.yaml" % tenant
    os.makedirs(os.path.dirname(tenant_secret_path), exist_ok=True)
    if (
            os.path.exists(tenant_secret_path) and
            "pkcs" in open(tenant_secret_path).read()):
        continue
    print("Generating secret for tenant %s" % tenant, file=sys.stderr)

    req = urllib.request.urlopen(inf["url"] + "/resources")
    data = json.loads(req.read().decode('utf-8'))
    tenant_config = data

    tenant_config_connection = inf["default-connection"]

    tenant_config_name = tenant_config["config-repo"][len(
        connections[tenant_config_connection]["base-url"]):]

    private_key_file = "/var/lib/zuul/keys/%s/%s.pem" % (
        tenant_config_connection, tenant_config_name)

    print("Looking for %s key on connection %s (%s)" % (
        tenant_config_name, tenant_config_connection, private_key_file),
        file=sys.stderr)

    for retry in range(1800):
        # Give zuul sometime to generate the key
        if os.path.exists(private_key_file):
            break
        time.sleep(1)
    if retry == 59:
        print("Couldn't find %s" % private_key_file)
        exit(1)

    tenant_config_secret = zuul_encrypt(
        private_key_file, "/var/lib/zuul/.ssh/id_rsa")
    open(tenant_secret_path, "w").write(tenant_config_secret)
    updated_keys.append(tenant_secret_path)

for updated_key in updated_keys:
    print(updated_key)
