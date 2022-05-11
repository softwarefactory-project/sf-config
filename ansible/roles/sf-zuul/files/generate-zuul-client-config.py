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

import requests
import subprocess
import sys
from urllib.parse import urljoin

i = iter(sys.argv)
args = [next(i, None) for _ in range(5)]

zuul_url = args[1]

if zuul_url is None:
    print("""
Usage: generate-zuul-client-config.py ZUUL_URL [username] [ttl] [output file]

Generate a zuul-client configuration file with a section for each tenant
on the Zuul instance. Each section comes with an admin token valid for <ttl>
seconds.

username default: cli_admin
token ttl default: 3600 seconds

if no output file is specified, print the configuration to stdout.
""")

username = args[2] or 'cli_admin'
token_ttl = args[3] or '3600'

verify_ssl = ('sftests.com' not in zuul_url)

config_file = args[4]

chunk_template = """
[{tenant}]
url={zuul_url}
verify_ssl={verify_ssl}
tenant={tenant}
auth_token={auth_token}"""


def get_tenants():
    try:
        tenants = requests.get(urljoin(zuul_url, 'api/tenants'),
                               verify='/etc/ssl/certs/ca-bundle.crt')
        tenants.raise_for_status()
        return [x['name'] for x in tenants.json()]
    except Exception:
        print("Could not connect to Zuul")
        raise


def get_token(tenant):
    cat = subprocess.Popen(
        ['zuul', 'create-auth-token',
         '--auth-config', 'zuul_operator',
         '--tenant', tenant, '--user', username,
         '--expires-in', token_ttl],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = cat.communicate()
    if not err:
        return out.decode().split(' ')[-1]
    raise Exception(err)


conf = ''

for tenant in get_tenants():
    auth_token = get_token(tenant)
    conf += chunk_template.format(tenant=tenant,
                                  zuul_url=zuul_url,
                                  verify_ssl=verify_ssl,
                                  auth_token=auth_token)

if config_file is None:
    print(conf)
else:
    with open(config_file, 'w') as cf:
        cf.write(conf)
