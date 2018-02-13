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
import random

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

    def get_or_generate_CA(self, args):
        args.ca_file = "%s/certs/localCA.pem" % args.lib
        args.ca_key_file = "%s/certs/localCAkey.pem" % args.lib
        args.ca_srl_file = "%s/certs/localCA.srl" % args.lib

        if not os.path.isfile(args.ca_file):
            # Generate a random OU subject to be able to trust multiple sf CA
            ou = ''.join(random.choice('0123456789abcdef') for n in range(6))
            execute(["openssl", "req", "-nodes", "-days", "3650", "-new",
                     "-x509", "-subj", "/C=FR/O=SoftwareFactory/OU=%s" % ou,
                     "-keyout", args.ca_key_file, "-out", args.ca_file])

        if not os.path.isfile(args.ca_srl_file):
            open(args.ca_srl_file, "w").write("00\n")

        args.glue["localCA_pem"] = open(args.ca_file).read()

    def get_or_generate_cert(self, args, name, common_name):
        cert_cnf = "%s/certs/%s.cnf" % (args.lib, name)
        cert_key = "%s/certs/%s.key" % (args.lib, name)
        cert_req = "%s/certs/%s.req" % (args.lib, name)
        cert_crt = "%s/certs/%s.crt" % (args.lib, name)
        cert_pem = "%s/certs/%s.pem" % (args.lib, name)

        def xunlink(filename):
            if os.path.isfile(filename):
                os.unlink(filename)

        if os.path.isfile(cert_cnf) and \
                open(cert_cnf).read().find("DNS.1 = %s\n" %
                                           args.sfconfig["fqdn"]) == -1:
            # if FQDN changed, remove all certificates
            for fn in [cert_cnf, cert_req, cert_crt]:
                xunlink(fn)

        # Then manage certificate request
        if not os.path.isfile(cert_cnf):
            open(cert_cnf, "w").write("""[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[ req_distinguished_name ]
commonName_default = %s

[ v3_req ]
subjectAltName=@alt_names

[alt_names]
DNS.1 = %s
""" % (common_name, common_name))

        if not os.path.isfile(cert_key):
            if os.path.isfile(cert_req):
                xunlink(cert_req)
            execute(["openssl", "genrsa", "-out", cert_key, "2048"])

        if not os.path.isfile(cert_req):
            if os.path.isfile(cert_crt):
                xunlink(cert_crt)
            execute(["openssl", "req", "-new", "-subj",
                     "/C=FR/O=SoftwareFactory/CN=%s" % args.sfconfig["fqdn"],
                     "-extensions", "v3_req", "-config", cert_cnf,
                     "-key", cert_key, "-out", cert_req])

        if not os.path.isfile(cert_crt):
            if os.path.isfile(cert_pem):
                xunlink(cert_pem)
            execute(["openssl", "x509", "-req", "-days", "3650", "-sha256",
                     "-extensions", "v3_req", "-extfile", cert_cnf,
                     "-CA", args.ca_file, "-CAkey", args.ca_key_file,
                     "-CAserial", args.ca_srl_file,
                     "-in", cert_req, "-out", cert_crt])

        if not os.path.isfile(cert_pem):
            open(cert_pem, "w").write("%s\n%s\n" % (
                open(cert_key).read(), open(cert_crt).read()))

        args.glue["%s_crt" % name] = open(cert_crt).read()
        args.glue["%s_key" % name] = open(cert_key).read()
        args.glue["%s_chain" % name] = args.glue["%s_crt" % name]

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
        args.glue["%s_mysql_user" % name] = user

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

    def validate(self, args, host):
        pass
