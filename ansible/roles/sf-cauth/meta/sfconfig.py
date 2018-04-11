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
import requests
import sys

from sfconfig.components import Component
from sfconfig.utils import execute


class Cauth(Component):
    def usage(self, parser):
        parser.add_argument("--set-idp-metadata", metavar="IDP_METADATA_URI",
                            help="Install the SAML2 Identity Provider and "
                                 "finish setting up the SAML2 authentication. "
                                 "The URI can be a file on the system or a "
                                 "URL (the distant server's certificate must "
                                 "be valid)")

    def argparse(self, args):
        if args.set_idp_metadata:
            self.idp_metadata_uri = args.set_idp_metadata
        else:
            self.idp_metadata_uri = None

    def configure(self, args, host):
        priv_file = "%s/certs/cauth_privkey.pem" % args.lib
        pub_file = "%s/certs/cauth_pubkey.pem" % args.lib
        if not os.path.isfile(priv_file):
            execute(["openssl", "genrsa", "-out", priv_file, "1024"])
        if not os.path.isfile(pub_file):
            execute(["openssl", "rsa", "-in", priv_file, "-out", pub_file,
                     "-pubout"])
        args.glue["cauth_privkey"] = open(priv_file).read()
        args.glue["cauth_pubkey"] = open(pub_file).read()
        self.add_mysql_database(args, "cauth")
        if self.idp_metadata_uri:
            if self.idp_metadata_uri.lower().startswith('http'):
                args.glue["idp_md_url"] = self.idp_metadata_uri
            else:
                args.glue["idp_md_file"] = self.idp_metadata_uri

    def validate(self, args, host):
        if not args.sfconfig["authentication"]["ldap"]["disabled"] and \
           not args.sfconfig["authentication"]["active_directory"]["disabled"]:
            print("Ldap and ActiveDirectory can't be enabled at the same time")
            exit(1)
