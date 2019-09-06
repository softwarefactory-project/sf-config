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

from sfconfig.components import Component
from sfconfig.utils import fail


class Keycloak(Component):
    def usage(self, parser):
        return

    def argparse(self, args):
        return

    def configure(self, args, host):
        self.add_mysql_database(args, "keycloak")
        if (
                bool(args.sfconfig["network"]["kc_tls_cert_file"]) !=
                bool(args.sfconfig["network"]["kc_tls_key_file"]) or
                bool(args.sfconfig["network"]["kc_tls_cert_file"]) !=
                bool(args.sfconfig["network"]["kc_tls_chain_file"])):
            fail("kc_tls_cert_file, kc_tls_key_file and kc_tls_chain_file "
                 "all need to be set")

        if args.sfconfig["network"]["kc_tls_cert_file"]:
            # Check file exists
            for k in ("kc_tls_cert_file", "kc_tls_chain_file",
                      "kc_tls_key_file"):
                if not os.path.isfile(args.sfconfig["network"][k]):
                    fail("%s: doesn't exist" %
                         args.sfconfig["network"][k])
            # Check key is secured
            if os.stat(
                    args.sfconfig["network"]
                    ["kc_tls_key_file"]).st_mode & 0o7077:
                fail("%s: insecure file mode, set to 0400" %
                     args.sfconfig["network"]["kc tls_key_file"])
            if os.stat(os.path.dirname(args.sfconfig[
                    "network"]["kc_tls_key_file"])).st_mode & 0o7077:
                fail("%s: insecure dir mode, set to 0700" %
                     os.path.dirname(args.sfconfig["network"]
                                                  ["kc_tls_key_file"]))
            # Use user-provided certificate for the gateway
            args.glue["keycloak_crt"] = open(
                args.sfconfig["network"]["kc_tls_cert_file"]).read()
            args.glue["keycloak_chain"] = open(
                args.sfconfig["network"]["kc_tls_chain_file"]).read()
            args.glue["keycloak_key"] = open(
                args.sfconfig["network"]["kc_tls_key_file"]).read()
        else:
            self.get_or_generate_cert(args, "keycloak",
                                      "keycloak." + args.sfconfig["fqdn"])
