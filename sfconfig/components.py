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

    def import_ssh_key(self, args, name, path):
        if not os.path.isfile(path):
            raise RuntimeError("%s: file doesn't exists" % path)

        if not os.path.isfile("%s.pub" % path):
            raise RuntimeError("%s: missing .pub file" % path)

        with open("%s/ssh_keys/%s" % (args.lib, name), "w") as of:
            of.write(open(path).read())
        with open("%s/ssh_keys/%s.pub" % (args.lib, name), "w") as of:
            of.write(open("%s.pub" % path).read())

    def get_or_generate_ssh_key(self, args, name):
        priv = "%s/ssh_keys/%s" % (args.lib, name)
        pub = "%s/ssh_keys/%s.pub" % (args.lib, name)

        if not os.path.isfile(priv):
            execute(["ssh-keygen", "-t", "rsa", "-N", "", "-f", priv, "-q"])
        args.glue[name] = open(priv).read()
        args.glue["%s_pub" % name] = open(pub).read()

    def add_mysql_database(self, args, name, hosts=[],
                           user=None, password=None):
        # Always enable localhost access
        if "localhost" not in hosts:
            hosts.append("localhost")
        service_host = args.glue["%s_host" % name]
        if service_host not in hosts:
            hosts.append(service_host)
        if user is None:
            user = name
        if password is None:
            password = args.secrets["%s_mysql_password" % name]
        args.glue.setdefault("mysql_databases", {})[name] = {
            'hosts': hosts,
            'user': user,
            'password': password,
        }
        args.glue["%s_mysql_host" % name] = args.glue["mysql_host"]

    def usage(self, parser):
        """Add argparse arguments"""
        pass

    def argparse(self, args):
        """Process argparse arguments"""
        pass

    def prepare(self, args):
        missing_roles = set()
        for role in self.require_roles:
            found = False
            for host in args.sfarch["inventory"]:
                if role in host["roles"]:
                    found = True
                    break
            if not found:
                missing_roles.add(role)
        if not args.allinone and missing_roles:
            raise RuntimeError("%s: missing required role %s" % (
                self.role, missing_roles))
        elif missing_roles:
            print("%s: Adding missing roles %s" % (self.role,
                                                   " ".join(missing_roles)))
            for role in missing_roles:
                args.sfarch["inventory"][0]["roles"].append(role)
            args.save_arch = True

    def configure(self, args, host):
        pass
