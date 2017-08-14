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

import base64
import os
import random

from sfconfig.components import Component
from sfconfig.utils import execute


def encode_image(path):
    return base64.b64encode(open(path).read())


class Gateway(Component):
    role = "gateway"

    def get_or_generate_localCA(self):
        ca_file = "%s/certs/localCA.pem" % self.args.lib
        ca_key_file = "%s/certs/localCAkey.pem" % self.args.lib
        ca_srl_file = "%s/certs/localCA.srl" % self.args.lib
        gateway_cnf = "%s/certs/gateway.cnf" % self.args.lib
        gateway_key = "%s/certs/gateway.key" % self.args.lib
        gateway_req = "%s/certs/gateway.req" % self.args.lib
        gateway_crt = "%s/certs/gateway.crt" % self.args.lib
        gateway_pem = "%s/certs/gateway.pem" % self.args.lib

        def xunlink(filename):
            if os.path.isfile(filename):
                os.unlink(filename)

        # First manage CA
        if not os.path.isfile(ca_file):
            # When CA doesn't exists, remove all certificates
            for fn in [gateway_cnf, gateway_req, gateway_crt]:
                xunlink(fn)
            # Generate a random OU subject to be able to trust multiple sf CA
            ou = ''.join(random.choice('0123456789abcdef') for n in range(6))
            execute(["openssl", "req", "-nodes", "-days", "3650", "-new",
                     "-x509", "-subj", "/C=FR/O=SoftwareFactory/OU=%s" % ou,
                     "-keyout", ca_key_file, "-out", ca_file])

        if not os.path.isfile(ca_srl_file):
            open(ca_srl_file, "w").write("00\n")

        if os.path.isfile(gateway_cnf) and \
                open(gateway_cnf).read().find("DNS.1 = %s\n" %
                                              self.sfmain["fqdn"]) == -1:
            # if FQDN changed, remove all certificates
            for fn in [gateway_cnf, gateway_req, gateway_crt]:
                xunlink(fn)

        # Then manage certificate request
        if not os.path.isfile(gateway_cnf):
            open(gateway_cnf, "w").write("""[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[ req_distinguished_name ]
commonName_default = %s

[ v3_req ]
subjectAltName=@alt_names

[alt_names]
DNS.1 = %s
""" % (self.sfmain["fqdn"], self.sfmain["fqdn"]))

        if not os.path.isfile(gateway_key):
            if os.path.isfile(gateway_req):
                xunlink(gateway_req)
            execute(["openssl", "genrsa", "-out", gateway_key, "2048"])

        if not os.path.isfile(gateway_req):
            if os.path.isfile(gateway_crt):
                xunlink(gateway_crt)
            execute(["openssl", "req", "-new", "-subj",
                     "/C=FR/O=SoftwareFactory/CN=%s" % self.sfmain["fqdn"],
                     "-extensions", "v3_req", "-config", gateway_cnf,
                     "-key", gateway_key, "-out", gateway_req])

        if not os.path.isfile(gateway_crt):
            if os.path.isfile(gateway_pem):
                xunlink(gateway_pem)
            execute(["openssl", "x509", "-req", "-days", "3650", "-sha256",
                     "-extensions", "v3_req", "-extfile", gateway_cnf,
                     "-CA", ca_file, "-CAkey", ca_key_file,
                     "-CAserial", ca_srl_file,
                     "-in", gateway_req, "-out", gateway_crt])

        if not os.path.isfile(gateway_pem):
            open(gateway_pem, "w").write("%s\n%s\n" % (
                open(gateway_key).read(), open(gateway_crt).read()))

        self.glue["localCA_pem"] = open(ca_file).read()
        self.glue["gateway_crt"] = open(gateway_crt).read()
        self.glue["gateway_key"] = open(gateway_key).read()
        self.glue["gateway_chain"] = self.glue["gateway_crt"]

    def configure(self):
        self.get_or_generate_localCA()
        self.glue["gateway_topmenu_logo_data"] = encode_image(
            "/etc/software-factory/logo-topmenu.png")
        self.glue["gateway_favicon_data"] = encode_image(
            "/etc/software-factory/logo-favicon.ico")
        self.glue["gateway_splash_image_data"] = encode_image(
            "/etc/software-factory/logo-splash.png")
        if "koji_host" in self.sfmain["network"] and \
           self.sfmain["network"]["koji_host"]:
            self.glue["koji_host"] = self.sfmain["network"]["koji_host"]
