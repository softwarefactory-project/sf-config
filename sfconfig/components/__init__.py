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


class Component(object):
    require_roles = []

    def get_or_generate_ssh_key(self, name):
        priv = "%s/ssh_keys/%s" % (self.args.lib, name)
        pub = "%s/ssh_keys/%s.pub" % (self.args.lib, name)

        if not os.path.isfile(priv):
            execute(["ssh-keygen", "-t", "rsa", "-N", "", "-f", priv, "-q"])
        self.glue[name] = open(priv).read()
        self.glue["%s_pub" % name] = open(pub).read()

    def add_mysql_database(self, name, hosts=[], user=None, password=None):
        # Always enable localhost access
        if "localhost" not in hosts:
            hosts.append("localhost")
        service_host = self.glue["%s_host" % name]
        if service_host not in hosts:
            hosts.append(service_host)
        if user is None:
            user = name
        if password is None:
            password = self.secrets["%s_mysql_password" % name]
        self.glue.setdefault("mysql_databases", {})[name] = {
            'hosts': hosts,
            'user': user,
            'password': password,
        }
        self.glue["%s_mysql_host" % name] = self.glue["mysql_host"]

    def argparse(self, parser):
        pass

    def prepare(self):
        missing_roles = set()
        for role in self.require_roles:
            if role not in self.arch["roles"]:
                missing_roles.add(role)
        if missing_roles:
            raise RuntimeError("%s: missing required role %s" % (
                self.role, missing_roles))

    def configure(self):
        pass
