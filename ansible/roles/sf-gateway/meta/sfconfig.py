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

from sfconfig.components import Component
from sfconfig.utils import fail


def encode_image(path):
    return base64.b64encode(open(path).read())


class Gateway(Component):
    def usage(self, parser):
        parser.add_argument("--disable-fqdn-redirection", action="store_true",
                            help="Do not redirect direct gateway access "
                            "to fqdn")

    def argparse(self, args):
        if args.disable_fqdn_redirection:
            args.glue["gateway_force_fqdn_redirection"] = False
        else:
            args.glue["gateway_force_fqdn_redirection"] = True

    def configure(self, args, host):
        if (
                bool(args.sfconfig["network"]["tls_cert_file"]) !=
                bool(args.sfconfig["network"]["tls_key_file"]) or
                bool(args.sfconfig["network"]["tls_cert_file"]) !=
                bool(args.sfconfig["network"]["tls_chain_file"])):
            fail("tls_cert_file, tls_key_file and tls_chain_file "
                 "all need to be set")

        if args.sfconfig["network"]["tls_cert_file"]:
            # Check file exists
            for k in ("tls_cert_file", "tls_chain_file", "tls_key_file"):
                if not os.path.isfile(args.sfconfig["network"][k]):
                    fail("%s: doesn't not exists" %
                         args.sfconfig["network"][k])
            # Check key is secured
            if os.stat(
                    args.sfconfig["network"]["tls_key_file"]).st_mode & 0o7077:
                fail("%s: insecure file mode, set to 0400" %
                     args.sfconfig["network"]["tls_key_file"])
            if os.stat(os.path.dirname(args.sfconfig[
                    "network"]["tls_key_file"])).st_mode & 0o7077:
                fail("%s: insecure dir mode, set to 0700" %
                     os.path.dirname(args.sfconfig["network"]["tls_key_file"]))
            # Use user-provided certificate for the gateway
            args.glue["gateway_crt"] = open(
                args.sfconfig["network"]["tls_cert_file"]).read()
            args.glue["gateway_chain"] = open(
                args.sfconfig["network"]["tls_chain_file"]).read()
            args.glue["gateway_key"] = open(
                args.sfconfig["network"]["tls_key_file"]).read()
        else:
            self.get_or_generate_cert(args, "gateway", args.sfconfig["fqdn"])
        args.glue["gateway_topmenu_logo_data"] = encode_image(
            "/etc/software-factory/logo-topmenu.png")
        args.glue["gateway_favicon_data"] = encode_image(
            "/etc/software-factory/logo-favicon.ico")
        args.glue["gateway_splash_image_data"] = encode_image(
            "/etc/software-factory/logo-splash.png")
        self.get_or_generate_ssh_key(args, "zuul_gatewayserver_rsa")
        args.glue["pagesuser_authorized_keys"] = []
        args.glue["pagesuser_authorized_keys"].append(
            args.glue["zuul_gatewayserver_rsa_pub"])
        if "koji_host" in args.sfconfig["network"] and \
           args.sfconfig["network"]["koji_host"]:
            args.glue["koji_host"] = args.sfconfig["network"]["koji_host"]
