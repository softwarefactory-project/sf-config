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

from sfconfig.components import Component


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
        self.get_or_generate_cert(args, "gateway", args.sfconfig["fqdn"])
        args.glue["gateway_topmenu_logo_data"] = encode_image(
            "/etc/software-factory/logo-topmenu.png")
        args.glue["gateway_favicon_data"] = encode_image(
            "/etc/software-factory/logo-favicon.ico")
        args.glue["gateway_splash_image_data"] = encode_image(
            "/etc/software-factory/logo-splash.png")
        args.glue["pagesuser_authorized_keys"] = []
        if "koji_host" in args.sfconfig["network"] and \
           args.sfconfig["network"]["koji_host"]:
            args.glue["koji_host"] = args.sfconfig["network"]["koji_host"]
