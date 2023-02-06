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
import urllib.parse

from sfconfig.components import Component
from sfconfig.utils import fail


def encode_image(path):
    return base64.b64encode(open(path, "rb").read()).decode()


class Gateway(Component):
    def usage(self, parser):
        parser.add_argument("--disable-ssl-redirection", action="store_true",
                            help="Do not redirect direct gateway access "
                            "to https://fqdn")

    def argparse(self, args):
        if args.disable_ssl_redirection:
            args.glue["gateway_force_ssl_redirection"] = False
        else:
            args.glue["gateway_force_ssl_redirection"] = True

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
            # Use user-provided certificate file path for the gateway
            for k in ("tls_cert_file", "tls_chain_file", "tls_key_file"):
                args.glue["gateway_" + k] = args.sfconfig["network"][k]
        else:
            self.get_or_generate_cert(args, "gateway", args.sfconfig["fqdn"])
        # TODO: add new welcome page support for that
        args.glue["gateway_topmenu_logo_data"] = encode_image(
            "/etc/software-factory/logo-topmenu.png")
        args.glue["gateway_favicon_data"] = encode_image(
            "/etc/software-factory/logo-favicon.ico")
        args.glue["gateway_splash_image_data"] = encode_image(
            "/etc/software-factory/logo-splash.png")
        args.glue["sf_context_info"]["header_logo_b64data"] = args.glue[
            "gateway_topmenu_logo_data"]
        args.glue["sf_context_info"]["splash_image_b64data"] = args.glue[
            "gateway_splash_image_data"]
        self.get_or_generate_ssh_key(args, "zuul_gatewayserver_rsa")
        args.glue["pagesuser_authorized_keys"] = []
        args.glue["pagesuser_authorized_keys"].append(
            args.glue["zuul_gatewayserver_rsa_pub"])
        if "koji_host" in args.sfconfig["network"] and \
           args.sfconfig["network"]["koji_host"]:
            args.glue["koji_host"] = args.sfconfig["network"]["koji_host"]
        if "tls_challenge_alias_path" in args.sfconfig["network"] and \
           args.sfconfig["network"]["tls_challenge_alias_path"]:
            args.glue["tls_challenge_alias_path"] = args.sfconfig["network"][
                "tls_challenge_alias_path"]
        if "apache_server_status" in args.sfconfig["network"] and \
                args.sfconfig["network"]["apache_server_status"]:
            args.glue["apache_server_status"] = args.sfconfig["network"][
                "apache_server_status"]

        args.glue['external_opensearch_host'] = None
        args.glue['external_opensearch_port'] = None

        config_key = 'external_opensearch'
        external_elk = args.sfconfig.get(config_key, {}).get('host')
        if external_elk:
            args.glue['external_opensearch_host'] = \
                urllib.parse.urlparse(external_elk).hostname
            args.glue['external_opensearch_port'] = \
                urllib.parse.urlparse(external_elk).port

        args.glue['external_opensearch_dashboards_host'] = \
            args.sfconfig.get('opensearch_dashboards', {}).get('host_url')
