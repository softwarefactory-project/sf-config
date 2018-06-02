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

from six.moves.urllib import request
from six.moves.urllib import parse

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
        self.resolve_config_location(args, host)
        self.resolve_zuul_jobs_location(args, host)
        if bool(args.sfconfig["tenant-deployment"]):
            # This is a tenant deployment, do extra configuration
            args.glue["tenant_name"] = args.sfconfig[
                "tenant-deployment"]["name"]
            args.glue["tenant_deployment"] = True
            args.glue["config_key_exists"] = False
            self.resolve_tenant_informations(args, host)
        else:
            # This is the master deployment, set default configuration
            args.glue["tenant_name"] = "local"
            args.glue["tenant_deployment"] = False
            # Master tenant deployment always has config key ready to be used
            args.glue["config_key_exists"] = True

    def ensure_git_connection(self, name, args, host):
        """When no gerrit or github is connection is configured,
           make sure local git connections are defined"""
        git_connections = args.glue.setdefault("zuul_git_connections", [])
        for git_connection in git_connections:
            if git_connection["name"] == name:
                return
        if name == "local-cgit":
            baseurl = "http://%s/cgit" % host["hostname"]
        else:
            baseurl = "file:///var/lib/software-factory/git"
        git_connections.append({
            "name": name,
            "baseurl": baseurl
        })

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
                conn_name = "gerrit"
                url = "%s/r/config" % args.glue["gateway_url"]
                conf_loc = "git+ssh://gerrit/config"
                jobs_loc = "git+ssh://gerrit/sf-jobs"
            else:
                if "cgit" in args.glue["roles"]:
                    conn_name = "local-cgit"
                    url = "%s/cgit/config" % args.glue["gateway_url"]
                else:
                    conn_name = "local-git"
                    url = "/var/lib/software-factory/git/config.git"
                # Inject zuul git connection
                self.ensure_git_connection(conn_name, args, host)

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
                        conn_name = conn["name"]
                        conf_name = project_name
                        conf_loc = "ssh://git@%s/%s" % (host, conf_name)
                    elif conn_name != conn["name"]:
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
                            conn_name = conn["name"]
                            conf_name = project_name
                            conf_loc = "%s/%s" % (conn_url, conf_name)
                        elif conn_name != conn["name"]:
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
        args.glue["config_connection_name"] = conn_name
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
                # Inject zuul git connection
                self.ensure_git_connection(zuul_conn, args, host)

        # Theses variable will be used in resources and zuul templates
        args.glue["zuul_jobs_connection_name"] = zuul_conn
        args.glue["zuul_jobs_project_name"] = zuul_name
        args.glue["zuul_jobs_location"] = zuul_loc

    def resolve_tenant_informations(self, args, host):
        """The goal of this method is fetch resources from master deployment
           and configure a zuul-less deployment"""

        args.glue["master_sf_fqdn"] = parse.urlparse(
            args.sfconfig["tenant-deployment"]["master-sf"]).hostname
        args.glue["master_sf_url"] = (
            parse.urlparse(
                args.sfconfig["tenant-deployment"]["master-sf"]).scheme +
            '://' + args.glue["master_sf_fqdn"])

        # Check master SF connectivity
        try:
            req = request.urlopen(
                "%s/manage/resources" %
                args.glue["master_sf_url"])
            master_resource = json.loads(req.read().decode('utf-8'))
        except Exception:
            fail("Couldn't contact master-sf: %s" % (
                args.glue["master_sf_url"]))

        # TODO: make sfconfig.yaml zuul setting usable without sf-zuul role
        args.glue["zuul_default_retry_attempts"] = args.sfconfig[
            "zuul"].get("default_retry_attempts", 3)

        # Fetch zuul public key from master sf - Needed for:
        # * For registering the master's zuul pub on the tenant's Gerrit
        # * For exposing the master's zuul pub key on the tenant /var/www/keys
        zuul_key_path = "%s/ssh_keys/master_zuul_rsa.pub" % args.lib
        try:
            zuul_key = open(zuul_key_path).read()
        except Exception:
            zuul_key = None
        if not zuul_key or "ssh-rsa" not in zuul_key:
            key_url = "%s/keys/zuul_rsa.pub" % args.glue["master_sf_url"]
            try:
                req = request.urlopen(key_url)
                zuul_key = req.read().decode("utf-8")
                open(zuul_key_path, "w").write(zuul_key)
            except Exception:
                fail("Couldn't get zuul public key at %s" % key_url)
        args.glue["zuul_rsa_pub"] = zuul_key

        # Look for master zuul-jobs project name and connection name
        try:
            # TODO: add special attribute to zuul-jobs to better identify it
            zj = master_resource.get(
                "resources", {}).get("projects", {}).get(
                    "internal", {}).get("source-repositories")[-1]
            zuul_name = list(zj.keys())[0]
            zuul_conn = zj[zuul_name]["connection"]
            args.glue["zuul_jobs_connection_name"] = zuul_conn
            args.glue["zuul_jobs_project_name"] = zuul_name
            args.glue["zuul_upstream_zuul_jobs"] = True
        except Exception:
            fail("Couldn't find zuul-jobs location in master sf")

        # Look for tenant default connection name and type to define
        # zuul connections on the master sf
        args.glue["zuul_gerrit_connections"] = []
        args.glue["zuul_github_connections"] = []
        args.glue["zuul_periodic_pipeline_mail_rcpt"] = args.sfconfig[
            "zuul"]["periodic_pipeline_mail_rcpt"]
        tenant_conf = master_resource.get(
            "resources", {}).get("tenants", {}).get(
                args.glue["tenant_name"])
        if tenant_conf and tenant_conf.get("default-connection"):
            args.glue["config_connection_name"] = \
                tenant_conf["default-connection"]
            for name, values in master_resource.get(
                    "resources", {}).get("connections", {}).items():

                if name == args.glue["config_connection_name"]:
                    if values.get("type") == "gerrit":
                        hostname = parse.urlparse(
                            values.get("base_url")).hostname
                        args.glue["zuul_gerrit_connections"].append(
                            {"name": args.glue["config_connection_name"],
                             "hostname": hostname,
                             "username": "zuul"}
                        )
                    elif values.get("type") == "github":
                        args.glue["zuul_github_connections"].append({
                            "name": name,
                            "app_id": values.get("github-app-name", ""),
                            "label_name": values.get("github-label", "")
                            })

        # Check if tenant config key already exists in master sf
        # If not then it means the tenant have not been defined yet on the
        # master sf. If yes, fetch it. The key will be used to initialize
        # Zuul's secrets (like logserver ssh key) into the tenant's sf
        # config repository.
        key_path = "/var/lib/software-factory/bootstrap-data/certs/config.pub"
        if (
                os.path.exists(key_path) and
                "PUBLIC KEY" in open(key_path).read()):
            args.glue["config_key_exists"] = True
        else:
            try:
                req = request.urlopen(
                    "%s/zuul/api/tenant/%s/key/%s.pub" % (
                        args.glue["master_sf_url"],
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

        # Fetch main install-server tenant-update secret to trigger zuul reload
        secret_path = "/var/lib/software-factory/bootstrap-data/certs/" \
                      "tenant-update-secret.yaml"
        if args.glue["config_key_exists"]:
            if (
                    os.path.exists(secret_path) and
                    "pkcs" in open(secret_path).read()):
                args.glue["tenant_update_secret"] = open(secret_path).read()
            else:
                try:
                    req = request.urlopen(
                        "%s/.config/tenant-update_%s_secret.yaml" % (
                            args.glue["master_sf_url"],
                            args.glue["tenant_name"]))
                    secret_data = req.read().decode("utf-8")
                    if "pkcs" in secret_data:
                        open(secret_path, "w").write(secret_data)
                        args.glue["tenant_update_secret"] = secret_data
                    else:
                        raise RuntimeError(
                            "Invalid secret --[%s]--" % secret_data)
                except Exception:
                    fail("Ooops, tenant-update secret hasn't been generated")
