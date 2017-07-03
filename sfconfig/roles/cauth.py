# Copyright (C) 2017 Red Hat
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

from sfconfig.utils import execute


def configure(args, host, sfconf, arch, glue, secrets, defaults):
    # Generate keys
    priv_file = "%s/certs/cauth_privkey.pem" % args.lib
    pub_file = "%s/certs/cauth_pubkey.pem" % args.lib
    if not os.path.isfile(priv_file):
        execute(["openssl", "genrsa", "-out", priv_file, "1024"])
    if not os.path.isfile(pub_file):
        execute(["openssl", "rsa", "-in", priv_file, "-out", pub_file,
                 "-pubout"])
    glue["cauth_privkey"] = open(priv_file).read()
    glue["cauth_pubkey"] = open(pub_file).read()
    glue["cauth_mysql_host"] = glue["mysql_host"]
    glue["mysql_databases"]["cauth"] = {
        'hosts': ['localhost', host["hostname"]],
        'user': 'cauth',
        'password': secrets['cauth_mysql_password'],
    }
