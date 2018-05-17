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

import json
import os

from sfconfig.components import Component
from sfconfig.utils import fail
from six.moves import urllib


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

        if args.sfconfig["tenant-deployment"] and (
                bool(args.sfconfig["tenant-deployment"]["name"]) !=
                bool(args.sfconfig["tenant-deployment"]["master-sf"])):
            fail("Both tenant name and master-sf url need to be set")
        if args.sfconfig["tenant-deployment"] and (
                "zuul" in args.glue["roles"] or
                "nodepool" in args.glue["roles"]):
            fail("Zuul and Nodepool can't be running in a tenant deployment")

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

        # Manage config and sf-jobs locations
        if not args.glue["remote_config_repositories"]:
            conf_name = "config"
            jobs_name = "sf-jobs"

            if "gerrit" in args.glue["roles"]:
                conn = "gerrit"
                url = "%s/r/config" % args.glue["gateway_url"]
                conf_loc = "git+ssh://gerrit/config"
                jobs_loc = "git+ssh://gerrit/sf-jobs"
            else:
                if "cgit" in args.glue["roles"]:
                    args.glue.setdefault("zuul_git_connections", []).append({
                        "name": "local-cgit",
                        "baseurl": "http://%s/cgit" % host["hostname"],
                    })
                    conn = "local-cgit"
                    url = "%s/cgit/config" % args.glue["gateway_url"]
                else:
                    args.glue.setdefault("zuul_git_connections", []).append({
                        "name": "local-git",
                        "baseurl": "file:///var/lib/software-factory/git"
                    })
                    conn = "local-git"
                    url = "/var/lib/software-factory/git/config.git"
                conf_loc = "/var/lib/software-factory/git/config.git"
                jobs_loc = "/var/lib/software-factory/git/sf-jobs.git"
        else:
            zuul_config = args.sfconfig['zuul']
            for repo in ('config-repo', 'jobs-repo'):
                location = args.sfconfig['config-locations'].get(repo)
                if repo == 'config-repo':
                    # We only need url location of the config repo,
                    # it's needed for config-update job
                    url = location
                found = False
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
                    for conn in zuul_config['gerrit_connections']:
                        conn_url = "ssh://%s@%s" % (
                            conn["username"], conn["hostname"])
                        url = conn.get('puburl')
                        if url not in location:
                            continue
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
                    fail("%s: No zuul connection configured" % location)

        args.glue["config_connection_name"] = conn
        args.glue["config_public_location"] = url
        args.glue["config_project_name"] = conf_name
        args.glue["config_location"] = conf_loc
        args.glue["sf_jobs_project_name"] = jobs_name
        args.glue["sf_jobs_location"] = jobs_loc

        # Manage zuul-jobs name and location
        if args.sfconfig["zuul"]["upstream_zuul_jobs"]:
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

        args.glue["zuul_jobs_connection_name"] = zuul_conn
        args.glue["zuul_jobs_project_name"] = zuul_name
        args.glue["zuul_jobs_location"] = zuul_loc

        key_path = "/var/lib/software-factory/bootstrap-data/certs/config.pub"
        master_path = "%s/ssh_keys/master_zuul_rsa.pub" % args.lib
        if bool(args.sfconfig["tenant-deployment"]):
            args.glue["tenant_deployment"] = True
            args.glue["tenant_name"] = args.sfconfig[
                "tenant-deployment"]["name"]
            args.glue["master_sf_url"] = args.sfconfig[
                "tenant-deployment"]["master-sf"].replace(
                    "https://", "").replace("http://", "")
            args.glue["master_sf_gateway"] = args.glue[
                "master_sf_url"].replace("/manage", "")

            # Adapt glue for zuul-less deployment
            args.glue["config_connection_name"] = args.sfconfig[
                "tenant-deployment"]["connection-name"]
            args.glue["zuul_default_retry_attempts"] = args.sfconfig[
                "zuul"].get("default_retry_attempts", 3)

            # Fetch zuul public key from master sf
            try:
                master_key = open(master_path).read()
            except Exception:
                master_key = None
            if not master_key or "ssh-rsa" not in master_key:
                key_url = "%s/keys/zuul_rsa.pub" % (
                    args.sfconfig["tenant-deployment"]["master-sf"].replace(
                        "/manage", ""))
                try:
                    req = urllib.request.urlopen(key_url)
                    master_key = req.read().decode("utf-8")
                    open(master_path, "w").write(master_key)
                except Exception:
                    fail("Couldn't get zuul public key at %s" % key_url)
            args.glue["zuul_rsa_pub"] = master_key

            # Fetch zuul-jobs project name and connection name
            # TODO: add special attribute to zuul-jobs to better identify it
            try:
                req = urllib.request.urlopen(
                    "%s/resources" %
                    args.sfconfig["tenant-deployment"]["master-sf"])
                master_resource = json.loads(req.read().decode('utf-8'))
                zj = master_resource.get(
                    "resources", {}).get("projects", {}).get(
                        "internal", {}).get("source-repositories")[-1]
                zuul_name = zj.keys()[0]
                zuul_conn = zj[zuul_name]["connection"]
                args.glue["zuul_jobs_connection_name"] = zuul_conn
                args.glue["zuul_jobs_project_name"] = zuul_name
                args.glue["zuul_upstream_zuul_jobs"] = True
            except Exception:
                raise
                fail("Couldn't find zuul-jobs location in master sf")

            # Look for connection type
            args.glue["zuul_gerrit_connections"] = []
            args.glue["zuul_github_connections"] = []
            args.glue["zuul_periodic_pipeline_mail_rcpt"] = args.sfconfig[
                "zuul"]["periodic_pipeline_mail_rcpt"]
            for name, values in master_resource.get(
                    "resources", {}).get("connections", {}).items():
                if name == args.glue["config_connection_name"]:
                    if values.get("type") == "gerrit":
                        args.glue["zuul_gerrit_connections"].append(
                            {'name': args.glue["config_connection_name"],
                             'hostname': "master-sf", "username": "zuul"}
                        )
                    elif values.get("type") == "github":
                        # TODO: add app name in main resource connection object
                        args.glue["zuul_github_connections"].append({
                            "name": name,
                            })

            # Check if tenant config key already exists in master sf
            args.glue["config_key_exists"] = False
            if (
                    os.path.exists(key_path) and
                    "PUBLIC KEY" in open(key_path).read()):
                args.glue["config_key_exists"] = True
            else:
                try:
                    req = urllib.request.urlopen(
                        "%s/zuul/api/tenant/%s/key/%s.pub" % (
                            args.sfconfig["tenant-deployment"][
                                "master-sf"].replace("/manage", ""),
                            args.glue["tenant_name"],
                            args.glue["config_project_name"]))
                    key_data = req.read().decode("utf-8")
                    if "PUBLIC KEY" in key_data:
                        open(key_path, "w").write(key_data)
                        args.glue["config_key_exists"] = True
                    else:
                        raise RuntimeError(
                            "Invalid public key --[%s]--" % key_data)
                except Exception:
                    print("Tenant isn't registered in master deployment, "
                          "add tenant config and restart sfconfig")
        else:
            args.glue["tenant_name"] = "local"
            args.glue["tenant_deployment"] = False
            # Master tenant deployment always has config key ready to be used
            args.glue["config_key_exists"] = True
