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
from sfconfig.utils import fail


class Cgit(Component):
    def validate(self, args, host):
        if "gerrit" in args.glue["roles"] and "gerrit" not in host["roles"]:
            fail("Cgit needs to be deployed on the same host as Gerrit.")
        elif "install-server" in args.glue["roles"] and \
             "install-server" not in host["roles"]:
            fail("Cgit needs to be deployed on the same host as "
                 "the install-server.")

    def configure(self, args, host):
        if "gerrit" not in args.glue["roles"]:
            args.glue["config_connection_name"] = "local-cgit"
            args.glue["zuul_jobs_connection_name"] = "local-cgit"
            args.glue["config_location"] = \
                "/var/lib/software-factory/git/config.git"
            args.glue["public_config_location"] = \
                "/var/lib/software-factory/git/config.git"
            args.glue["sf_jobs_location"] = \
                "/var/lib/software-factory/git/sf-jobs.git"
            args.glue["zuul_jobs_location"] = \
                "/var/lib/software-factory/git/zuul-jobs.git"
            args.glue["public_config_location"] = "%s/cgit/config" % (
                args.glue["gateway_url"])
