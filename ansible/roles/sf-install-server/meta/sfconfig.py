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
    def validate(self, args, host):
        if bool(args.sfconfig['config-locations']['config-repo']) != \
           bool(args.sfconfig['config-locations']['jobs-repo']):
            fail("Both config-repo and jobs-repo needs to be set")

    def configure(self, args, host):
        self.get_or_generate_CA(args)
        self.get_or_generate_ssh_key(args, "service_rsa")
        self.get_or_generate_ssh_key(args, "zuul_worker_rsa")

        args.glue["sf_version"] = get_sf_version()
        args.glue["sf_previous_version"] = get_previous_version()

        if "gerrit" not in args.glue["roles"] or \
           "cgit" not in args.glue["roles"]:
            args.glue["config_connection_name"] = "local-git"
            args.glue["config_location"] = \
                "/var/lib/software-factory/git/config.git"
            args.glue["public_config_location"] = \
                "/var/lib/software-factory/git/config.git"
            args.glue["sf_jobs_location"] = \
                "/var/lib/software-factory/git/sf-jobs.git"
            args.glue["zuul_jobs_location"] = \
                "/var/lib/software-factory/git/zuul-jobs.git"

        args.glue["config_project_name"] = "config"
        args.glue["jobs_project_name"] = "sf-jobs"
        args.glue["remote_config_repositories"] = False

        zuul_config = args.sfconfig['zuul']
        for repo in ('config-repo', 'jobs-repo'):
            location = args.sfconfig['config-locations'].get(repo)
            if not location:
                continue
            args.glue["remote_config_repositories"] = True
            found = False
            for conn in zuul_config['github_connections']:
                host = conn.get('hostname', 'github.com')
                if host not in location:
                    continue
                # Project name is the last two components
                project_name = "/".join(location.split('/')[-2:])
                if repo == "config-repo":
                    args.glue["config_connection_name"] = conn["name"]
                    args.glue["config_project_name"] = project_name
                    args.glue["config_location"] = "ssh://git@%s/%s" % (
                        host, args.glue["config_project_name"])
                elif args.glue["config_connection_name"] != conn["name"]:
                    fail("Config and jobs needs to share "
                         "the same connection")
                else:
                    args.glue["jobs_project_name"] = project_name
                    args.glue["sf_jobs_location"] = "ssh://git@%s/%s" % (
                        host, args.glue["jobs_project_name"])
                found = True
                break

            if not found:
                for conn in zuul_config['gerrit_connections']:
                    url = conn.get('puburl')
                    if url not in location:
                        continue
                    project_name = location[len(url):]
                    if repo == "config-repo":
                        args.glue["config_connection_name"] = conn["name"]
                        args.glue["config_project_name"] = project_name
                        args.glue["config_location"] = "ssh://%s@%s/%s" % (
                            conn["username"], conn["hostname"], project_name)
                    elif args.glue["config_connection_name"] != conn["name"]:
                        fail("Config and jobs needs to share "
                             "the same connection")
                    else:
                        args.glue["jobs_project_name"] = project_name
                        args.glue["sf_jobs_location"] = "ssh://%s@%s/%s" % (
                            conn["username"], conn["hostname"], project_name)
                    found = True
                    break

            if not found:
                fail("%s: No zuul connection configured" % location)
