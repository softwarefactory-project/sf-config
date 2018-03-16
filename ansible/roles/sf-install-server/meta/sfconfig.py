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


def get_sf_version():
    try:
        return open("/etc/sf-release").read().strip()
    except IOError:
        return "master"


def get_previous_version():
    try:
        ver = float(open("/var/lib/software-factory/.version").read().strip())
        if ver == '':
            raise IOError
    except:
        print("WARNING: couldn't read previous version, defaulting to 2.6")
        ver = 2.6
    return ver


class InstallServer(Component):
    def usage(self, parser):
        parser.add_argument("--remote-zuul-url",
                            help="The zuul-web url of a remote zuul service")
        parser.add_argument("--tenant-name",
                            help="The name of the remote zuul tenant")
        parser.add_argument("--config-repo-url",
                            help="The url of the tenant config repository")
        parser.add_argument("--config-repo-name",
                            help="The config repo name defined in "
                                 "zuul main.yaml")

    def argparse(self, args):
        if args.remote_zuul_url:
            args.glue["remote_zuul_url"] = args.remote_zuul_url
            if args.tenant_name is None:
                fail("--tenant_name is required")
            args.glue["sf_tenant_name"] = args.tenant_name
            if args.config_repo_url is None:
                fail("--config-repo-url is required")
            args.glue["config_repo_url"] = args.config_repo_url
            args.glue["internal_config_repo_url"] = args.config_repo_url
            if args.config_repo_name is None:
                fail("--config-repo-name is required")
            args.glue["config_repo_name"] = args.config_repo_name
        else:
            if args.tenant_name is not None or \
               args.config_repo_url is not None or \
               args.config_repo_name is not None:
                    fail("--remote-zuul-url is required")

    def configure(self, args, host):
        self.get_or_generate_CA(args)
        self.get_or_generate_ssh_key(args, "service_rsa")
        self.get_or_generate_ssh_key(args, "jenkins_rsa")
        self.get_or_generate_ssh_key(args, "zuul_worker_rsa")

        args.glue["sf_version"] = get_sf_version()
        args.glue["sf_previous_version"] = get_previous_version()
