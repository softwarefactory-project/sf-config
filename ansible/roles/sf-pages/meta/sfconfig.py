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

from sfconfig.components import Component


class Pages(Component):
    role = "pages"

    def configure(self, args, host):
        args.glue["pages"] = {
            "name": "pages",
            "host": args.glue["pages_host"],
            "user": "pagesuser",
            "path": "/var/www/html/pages",
        }
        args.glue["pagesuser_authorized_keys"] = []
        if "zuul-launcher" in args.glue["roles"]:
            args.glue["pagesuser_authorized_keys"].append(
                args.glue["jenkins_rsa_pub"])
        if "zuul3-executor" in args.glue["roles"]:
            args.glue["pagesuser_authorized_keys"].append(
                args.glue["zuul_rsa_pub"])
