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

import base64
import os
import random

from sfconfig.utils import execute


def encode_image(path):
    return base64.b64encode(open(path).read())


def configure(args, host, sfconf, arch, glue, secrets, defaults):
    ca_file = "%s/certs/localCA.pem" % args.lib
    ca_key_file = "%s/certs/localCAkey.pem" % args.lib
    ca_srl_file = "%s/certs/localCA.srl" % args.lib
    gateway_cnf = "%s/certs/gateway.cnf" % args.lib
    gateway_key = "%s/certs/gateway.key" % args.lib
    gateway_req = "%s/certs/gateway.req" % args.lib
    gateway_crt = "%s/certs/gateway.crt" % args.lib
    gateway_pem = "%s/certs/gateway.pem" % args.lib

    def xunlink(filename):
        if os.path.isfile(filename):
            os.unlink(filename)

    # First manage CA
    if not os.path.isfile(ca_file):
        # When CA doesn't exists, remove all certificates
        for fn in [gateway_cnf, gateway_req, gateway_crt]:
            xunlink(fn)
        # Generate a random OU subject to be able to trust multiple sf CA
        ou = ''.join(random.choice('0123456789abcdef') for n in xrange(6))
        execute(["openssl", "req", "-nodes", "-days", "3650", "-new",
                 "-x509", "-subj", "/C=FR/O=SoftwareFactory/OU=%s" % ou,
                 "-keyout", ca_key_file, "-out", ca_file])

    if not os.path.isfile(ca_srl_file):
        open(ca_srl_file, "w").write("00\n")

    if os.path.isfile(gateway_cnf) and \
            open(gateway_cnf).read().find("DNS.1 = %s\n" %
                                          sfconf["fqdn"]) == -1:
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
""" % (sfconf["fqdn"], sfconf["fqdn"]))

    if not os.path.isfile(gateway_key):
        if os.path.isfile(gateway_req):
            xunlink(gateway_req)
        execute(["openssl", "genrsa", "-out", gateway_key, "2048"])

    if not os.path.isfile(gateway_req):
        if os.path.isfile(gateway_crt):
            xunlink(gateway_crt)
        execute(["openssl", "req", "-new", "-subj",
                 "/C=FR/O=SoftwareFactory/CN=%s" % sfconf["fqdn"],
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

    glue["localCA_pem"] = open(ca_file).read()
    glue["gateway_crt"] = open(gateway_crt).read()
    glue["gateway_key"] = open(gateway_key).read()
    glue["gateway_chain"] = glue["gateway_crt"]
    glue["gateway_topmenu_logo_data"] = encode_image(
        "/etc/software-factory/logo-topmenu.png")
    glue["gateway_favicon_data"] = encode_image(
        "/etc/software-factory/logo-favicon.ico")
    glue["gateway_splash_image_data"] = encode_image(
        "/etc/software-factory/logo-splash.png")
    glue["gateway_url"] = "https://%s" % sfconf["fqdn"]
