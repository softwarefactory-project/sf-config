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
    def configure(self, args, host):
        self.get_or_generate_CA(args)
        self.get_or_generate_ssh_key(args, "service_rsa")
        self.get_or_generate_ssh_key(args, "zuul_worker_rsa")
        self.get_or_generate_ssh_key(args, "admin_rsa")

        args.glue["sf_version"] = get_sf_version()
        args.glue["sf_previous_version"] = get_previous_version()
