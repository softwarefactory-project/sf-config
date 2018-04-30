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

        if bool(args.sfconfig['config-locations']['config-repo']):
            args.glue["remote_config_repositories"] = True
        else:
            args.glue["remote_config_repositories"] = False
        self.resolve_config_location(args, host)
        self.resolve_zuul_jobs_location(args, host)

    def resolve_config_location(self, args, host):
        """The goal of this method is to discover the config and sf-jobs
           location and their associated connection
        """
        if not args.glue["remote_config_repositories"]:
            # When config repositories are local, default names are config
            # and sf-jobs
            conf_name = "config"
            jobs_name = "sf-jobs"

            if "gerrit" in args.glue["roles"]:
                # If gerrit is enabled, use it's connection and default push
                # location
                conn = "gerrit"
                url = "%s/r/config" % args.glue["gateway_url"]
                conf_loc = "git+ssh://gerrit/config"
                jobs_loc = "git+ssh://gerrit/sf-jobs"
            else:
                if "cgit" in args.glue["roles"]:
                    # Inject a cgit connection into zuul configuration
                    args.glue.setdefault("zuul_git_connections", []).append({
                        "name": "local-cgit",
                        "baseurl": "http://%s/cgit" % host["hostname"],
                    })
                    conn = "local-cgit"
                    url = "%s/cgit/config" % args.glue["gateway_url"]
                else:
                    # Inject a file:// connection into zuul configuration
                    args.glue.setdefault("zuul_git_connections", []).append({
                        "name": "local-git",
                        "baseurl": "file:///var/lib/software-factory/git"
                    })
                    conn = "local-git"
                    url = "/var/lib/software-factory/git/config.git"
                # If gerrit is not enabled, push location is a local path
                conf_loc = "/var/lib/software-factory/git/config.git"
                jobs_loc = "/var/lib/software-factory/git/sf-jobs.git"
        else:
            # When config repositories are remote, we need to look for the
            # zuul connection name.
            zuul_config = args.sfconfig['zuul']
            for repo in ('config-repo', 'jobs-repo'):
                location = args.sfconfig['config-locations'].get(repo)
                if repo == 'config-repo':
                    # We only need url location of the config repo,
                    # it's needed for config-update job
                    url = location
                found = False
                # First we look for a matching github connections
                for conn in zuul_config['github_connections']:
                    host = conn.get('hostname', 'github.com')
                    if host not in location:
                        continue
                    # Project name is the last two components
                    project_name = "/".join(location.split('/')[-2:])
                    if repo == "config-repo":
                        conn = conn["name"]
                        conf_name = project_name
                        conf_loc = "ssh://git@%s/%s" % (host, conf_name)
                    elif conn != conn["name"]:
                        fail("Config and jobs needs to share "
                             "the same connection")
                    else:
                        jobs_name = project_name
                        jobs_loc = "ssh://git@%s/%s" % (host, jobs_name)
                    found = True
                    break

                if not found:
                    # If location is matching github connections, look for
                    # available gerrit connections.
                    for conn in zuul_config['gerrit_connections']:
                        conn_url = "ssh://%s@%s" % (
                            conn["username"], conn["hostname"])
                        url = conn.get('puburl')
                        if url not in location:
                            continue
                        # Project name is the remaining part after the puburl
                        project_name = location[len(url):]
                        if repo == "config-repo":
                            conn = conn["name"]
                            conf_name = project_name
                            conf_loc = "%s/%s" % (conn_url, conf_name)
                        elif conn != conn["name"]:
                            fail("Config and jobs needs to share "
                                 "the same connection")
                        else:
                            jobs_name = project_name
                            jobs_loc = "%s/%s" % (conn_url, jobs_name)
                        found = True
                        break

                if not found:
                    # We couldn't find a zuul connection for remote locations
                    fail("%s: No zuul connection configured" % location)

        # Theses variable will be used in resources and zuul templates
        args.glue["config_connection_name"] = conn
        args.glue["config_public_location"] = url
        args.glue["config_project_name"] = conf_name
        args.glue["config_location"] = conf_loc
        args.glue["sf_jobs_project_name"] = jobs_name
        args.glue["sf_jobs_location"] = jobs_loc

    def resolve_zuul_jobs_location(self, args, host):
        """The goal of this method is to discover the zuul-jobs location and
           it's associated connection"""
        if args.sfconfig["zuul"]["upstream_zuul_jobs"]:
            # When using the upstream project, look for the connection name
            zuul_name = "openstack-infra/zuul-jobs"
            zuul_loc = "https://git.openstack.org/openstack-infra/zuul-jobs"
            zuul_conn = None
            # Check if review.openstack.org is configured
            for connection in args.sfconfig.get("zuul", {}).get(
                    "gerrit_connections", []):
                if connection["hostname"] == "review.openstack.org":
                    zuul_conn = connection["name"]
                    break
            if not zuul_conn:
                # Check if git.openstack.org is configured
                for connection in args.sfconfig.get("zuul", {}).get(
                        "git_connections", []):
                    if "git.openstack.org" in connection["baseurl"]:
                        zuul_conn = connection["name"]
                        break
            if not zuul_conn:
                fail("To use upstream zuul-jobs, configure connection to the"
                     " remote git")
        else:
            # When using the zuul-jobs copy, set the right connection name
            zuul_name = "zuul-jobs"
            if "gerrit" in args.glue["roles"]:
                zuul_loc = "git+ssh://gerrit/zuul-jobs"
                zuul_conn = "gerrit"
            else:
                zuul_loc = "/var/lib/software-factory/git/zuul-jobs.git"
                if "cgit" in args.glue["roles"]:
                    zuul_conn = "local-cgit"
                else:
                    zuul_conn = "local-git"

        # Theses variable will be used in resources and zuul templates
        args.glue["zuul_jobs_connection_name"] = zuul_conn
        args.glue["zuul_jobs_project_name"] = zuul_name
        args.glue["zuul_jobs_location"] = zuul_loc
