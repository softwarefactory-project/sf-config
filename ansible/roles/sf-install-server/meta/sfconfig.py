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
import ssl

import urllib.error
import urllib.parse
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
    except Exception:
        print("WARNING: couldn't read previous version, defaulting to master")
        ver = 9999.
    return ver


def create_context_info(fqdn, tenant, roles, auth, sf_version, custom_links,
                        args):
    def service(name, path):
        if name in roles or (
                name == "opensearch-dashboards" and
                "opensearch_dashboards" in args.sfconfig and
                args.sfconfig['opensearch_dashboards'].get('host_url', "")
                ):
            return [dict(name=name, path=path)]
        else:
            return []

    def auth_other(name):
        return [dict(name=name, text=auth[name].get(
            "login_button_text", ""))] if not auth.get(name, {}).get(
                "disabled", True) else []

    def auth_oauth(name):
        return [name] if not auth.get("oauth2", {}).get(name, {}).get(
            "disabled", True) else []

    def get_links(_type):
        if _type == "documentation":
            documentation_default_links = [
                {"name": "Software Factory", "link": "/docs"},
                {"name": "Zuul", "link": "/docs/zuul"},
                {"name": "Nodepool", "link": "/docs/nodepool"}
            ]
            return (
                documentation_default_links +
                custom_links.get("documentation_links", [])
            )
        elif _type == "status":
            return custom_links.get("status_links", [])
        elif _type == "contact":
            return custom_links.get("contact_links", [])
        else:
            raise

    status_link = [] if tenant else [dict(name="status", path="/status")]

    return dict(
        version=sf_version,
        links={
            "documentation": get_links("documentation"),
            "status": get_links("status"),
            "contact": get_links("contact"),
        },
        services=(
            []
            # FIXME "SF" is a set variable in the playbooks. This should
            # remain a constant but it might be good to be able to set
            # it arbitrarily.
            #
            # (also, list keycloak here so that the auth service
            # is shown first)
            + service("gerrit", "/r/")
            + [dict(name="zuul", path="/zuul")]
            + status_link
            + service("nodepool", "/nodepool")
            + service("keycloak", "/auth/realms/SF/account/")
            + service("opensearch-dashboards", "/analytics")
            + service("grafana", "/grafana")
            + service("etherpad", "/etherpad")
            + service("lodgeit", "/paste")
            + service("hound", "/codesearch")
            + service("cgit", "/cgit")
            + service("murmur", "mumble://" + fqdn + "/?version=1.2.0")
        ),
        # TODO this is kept for compatibility with the re-sf library.
        auths=dict(
            oauth=(
                []
            ),
            other=(
                []
            )))


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
        self.get_or_generate_ssh_key(args, "zuul_worker_rsa")
        # When install-server is hosted on the gateway, we can use fqdn instead
        args.glue["install_server_hostname"] = args.glue["install_server_host"]
        if args.glue["install_server_host"] == args.glue["gateway_host"]:
            args.glue["install_server_hostname"] = args.sfconfig["fqdn"]

        args.glue["sf_version"] = get_sf_version()
        args.glue["sf_previous_version"] = get_previous_version()
        if args.upgrade:
            print("Going to upgrade from %s to %s" % (
                args.glue["sf_previous_version"], args.glue["sf_version"]))

        if bool(args.sfconfig['config-locations']['config-repo']):
            args.glue["remote_config_repositories"] = True
        else:
            args.glue["remote_config_repositories"] = False
            args.glue["sync_strategy"] = 'push'

        args.glue["sync_strategy"] = args.sfconfig['config-locations'][
            'strategy'].get('sync', 'push')
        if args.glue["sync_strategy"] not in ('push', 'patch', 'review'):
            fail("Only push or patch or review sync strategy is supported.")

        args.glue["resources_connections"] = {'__force_dict__': True}

        if bool(args.sfconfig["tenant-deployment"]):
            args.glue["tenant_name"] = args.sfconfig[
                "tenant-deployment"]["name"]
            # Import master sf connections
            self.read_master_sf_resources(args, host)

        self.resolve_config_location(args, host)
        self.resolve_zuul_jobs_location(args, host)

        # Assume the config key has been initialized
        args.glue["config_key_initialized"] = True
        change_url_path = "change/{change.number},{change.patchset}"
        if bool(args.sfconfig["tenant-deployment"]):
            # This is a tenant deployment, do extra configuration
            args.glue["build_status_page_url"] = "%s/zuul/status/%s" % (
                args.glue["gateway_url"], change_url_path)
            args.glue["build_result_page_url"] = \
                "%s/zuul/buildset/{buildset.uuid}" % (
                    args.glue["gateway_url"])
            args.glue["tenant_zuul_api"] = "%s/zuul/api" % (
                args.glue["gateway_url"])
            args.glue["tenant_deployment"] = True
            self.resolve_tenant_informations(args, host)
        else:
            if "zuul" not in args.glue["roles"]:
                fail("Zuul service is required in non tenant-deployment mode")
            # This is the master deployment, set default configuration
            args.glue["tenant_name"] = args.sfconfig["default-tenant-name"]
            args.glue[
                "build_status_page_url"] = "%s/zuul/t/%s/status/%s" % (
                    args.glue["gateway_url"], args.glue["tenant_name"],
                    change_url_path)
            args.glue[
                "build_result_page_url"] = \
                "%s/zuul/t/%s/buildset/{buildset.uuid}" % (
                        args.glue["gateway_url"], args.glue["tenant_name"])
            args.glue["tenant_zuul_api"] = "%s/zuul/api/tenant/%s" % (
                args.glue["gateway_url"], args.glue["tenant_name"])
            args.glue["tenant_deployment"] = False
            self.resolve_config_key(args,
                                    "%s/key/%s.pub" % (
                                        args.glue["tenant_zuul_api"],
                                        args.glue["config_project_name"]))

        args.glue["sf_context_info"] = create_context_info(
            args.sfconfig["fqdn"],
            args.glue["tenant_deployment"],
            args.glue["roles"],
            args.sfconfig["authentication"],
            args.glue["sf_version"],
            args.sfconfig.get("custom_links", {}),
            args)

        # Convert sfconfig.yaml connections into group vars
        zuul_config = args.sfconfig.get("zuul", {})
        args.glue.setdefault("zuul_ssh_known_hosts", [])
        args.glue.setdefault("zuul_gerrit_connections", [])
        args.glue.setdefault("zuul_github_connections", [])
        args.glue.setdefault("zuul_pagure_connections", [])
        args.glue.setdefault("zuul_gitlab_connections", [])
        args.glue.setdefault("zuul_git_connections", [])

        args.glue.setdefault(
            "zuul_external_authenticators",
            args.sfconfig.get("zuul", {}).get("external_authenticators", []),
        )

        # Manage default pods
        args.glue.setdefault("nodepool_default_pods", args.sfconfig.get(
            "nodepool", {}).get("k1s_default_pods", True))
        if (
                args.glue["nodepool_default_pods"] and
                "hypervisor-k1s" in args.glue["roles"]):
            args.sfconfig["zuul"]["default_nodeset_label"] = "pod-stream-9"
        args.glue["zuul_default_nodeset_label"] = \
            args.sfconfig["zuul"].get("default_nodeset_label", "pod-stream-9")
        args.glue["zuul_default_nodeset_name"] = \
            args.sfconfig["zuul"].get("default_nodeset_name", "container")

        # Add local gerrit if available
        if "gerrit" in args.glue["roles"]:
            args.glue["gerrit_pub_url"] = "%s/r/" % args.glue["gateway_url"]
            puburl = args.glue["gerrit_pub_url"]
            if puburl[-1] == "/":
                puburl = puburl[:-1]
            if not args.glue["tenant_deployment"]:
                # Do not add local gerrit here because we got it from master
                args.glue["zuul_gerrit_connections"].append({
                    'name': "gerrit",
                    'port': 29418,
                    'hostname': args.glue["gerrit_host"],
                    'canonical_hostname': args.sfconfig["fqdn"],
                    'puburl': puburl,
                    'username': 'zuul',
                    'password': args.glue['gerrit_zuul_password']
                })

        if not args.sfconfig["network"]["disable_external_resources"]:
            for extra_gerrit in zuul_config.get("gerrit_connections", []):
                if extra_gerrit.get("port", 29418) == 22:
                    host_packed = extra_gerrit["hostname"]
                else:
                    host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                               extra_gerrit.get("port", 29418))
                args.glue["zuul_ssh_known_hosts"].append({
                    "host_packed": host_packed,
                    "host": extra_gerrit["hostname"],
                    "port": extra_gerrit.get("port", 29418)
                })
                args.glue["zuul_gerrit_connections"].append(extra_gerrit)
            for github_connection in zuul_config.get("github_connections", []):
                if github_connection.get("port", 22) == 22:
                    host_packed = github_connection.get(
                        "hostname", "github.com")
                else:
                    host_packed = "[%s]:%s" % (github_connection["hostname"],
                                               github_connection["port"])
                args.glue["zuul_ssh_known_hosts"].append({
                    "host_packed": host_packed,
                    "host": github_connection.get("hostname", "github.com"),
                    "port": github_connection.get("port", 22)
                })
                args.glue["zuul_github_connections"].append(github_connection)
                gh_app_key = github_connection.get('app_key')
                if gh_app_key and os.path.isfile(gh_app_key):
                    github_connection['app_key'] = open(gh_app_key).read()
            for pagure_connection in zuul_config.get("pagure_connections", []):
                host_packed = pagure_connection.get("hostname", "pagure.io")
                args.glue["zuul_ssh_known_hosts"].append({
                    "host_packed": host_packed,
                    "host": pagure_connection.get("hostname", "pagure.io"),
                    "port": 22
                })
                if not pagure_connection.get("baseurl"):
                    pagure_connection["baseurl"] = (
                        'https://%s' % pagure_connection.get(
                            'hostname', 'pagure.io'))
                args.glue["zuul_pagure_connections"].append(pagure_connection)
            for gitlab_connection in zuul_config.get("gitlab_connections", []):
                host_packed = gitlab_connection.get("hostname", "gitlab.com")
                args.glue["zuul_ssh_known_hosts"].append({
                    "host_packed": host_packed,
                    "host": gitlab_connection.get("hostname", "gitlab.com"),
                    "port": 22
                })
                if not gitlab_connection.get("baseurl"):
                    gitlab_connection["baseurl"] = (
                        'https://%s' % gitlab_connection.get(
                            'hostname', 'gitlab.com'))
                args.glue["zuul_gitlab_connections"].append(gitlab_connection)
            for git_connection in zuul_config.get("git_connections", []):
                args.glue["zuul_git_connections"].append(git_connection)

        # Set auto-configurations of pipelines list
        args.glue.setdefault("zuul_gerrit_connections_pipelines", [])
        args.glue.setdefault("zuul_github_connections_pipelines", [])
        args.glue.setdefault("zuul_pagure_connections_pipelines", [])
        args.glue.setdefault("zuul_gitlab_connections_pipelines", [])
        args.glue["zuul_gate_pipeline"] = False

        for gerrit_connection in args.glue["zuul_gerrit_connections"]:
            if not gerrit_connection.get("default_pipelines", True) or \
                    gerrit_connection.get("report_only", False):
                continue
            args.glue["zuul_gerrit_connections_pipelines"].append(
                gerrit_connection)
            args.glue["zuul_gate_pipeline"] = True
        for github_connection in args.glue["zuul_github_connections"]:
            if not github_connection.get("default_pipelines", True):
                continue
            args.glue["zuul_github_connections_pipelines"].append(
                github_connection)
            if github_connection.get("app_name"):
                args.glue["zuul_gate_pipeline"] = True
        for pagure_connection in args.glue["zuul_pagure_connections"]:
            if not pagure_connection.get("default_pipelines", True):
                continue
            args.glue["zuul_pagure_connections_pipelines"].append(
                pagure_connection)
            args.glue["zuul_gate_pipeline"] = True
        for gitlab_connection in args.glue["zuul_gitlab_connections"]:
            if not gitlab_connection.get("default_pipelines", True):
                continue
            args.glue["zuul_gitlab_connections_pipelines"].append(
                gitlab_connection)
            args.glue["zuul_gate_pipeline"] = True

        # NOTE: Needed by ci-log-processing and elasticsearch/opensearch
        config_key = 'external_opensearch'
        args.glue['external_opensearch_suffix'] = \
            args.sfconfig.get(config_key, {}).get('suffix')
        external_elk = args.sfconfig.get(config_key, {}).get('host')
        if external_elk:
            args.glue['external_opensearch_host'] = \
                urllib.parse.urlparse(external_elk).hostname
            args.glue['external_opensearch_port'] = \
                urllib.parse.urlparse(external_elk).port
        else:
            args.glue['external_opensearch_host'] = None
            args.glue['external_opensearch_port'] = None

        args.glue['external_opensearch_cacert'] = \
            args.sfconfig.get(config_key, {}).get('cacert_path')
        args.glue['external_opensearch_users'] = \
            args.sfconfig.get(config_key, {}).get('users')

    def resolve_config_key(self, args, url):
        """The goal of this method is to check and ensure we have the correct
        zuul public key for the config project to pre-generate secrets."""
        key_path = "/var/lib/software-factory/bootstrap-data/certs/config.pub"
        key_data = ""
        args.glue["config_key_path"] = key_path
        args.glue["config_key_url"] = url
        args.glue["config_key_exists"] = False
        args.glue["config_key_changed"] = True
        if os.path.exists(key_path):
            key_data = open(key_path).read()
        try:
            req = request.urlopen(url)
            current_data = req.read().decode("utf-8")
            if "PUBLIC KEY" not in current_data:
                raise RuntimeError(
                    "Invalid public key --[%s]--" % current_data)
            args.glue["config_key_exists"] = True
            args.glue["config_key_changed"] = current_data != key_data
            if args.glue["config_key_changed"]:
                with open(key_path, "w") as of:
                    of.write(current_data)
        except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                ssl.CertificateError):
            print("%s: config key not available" % url)
            if "PUBLIC KEY" in key_data:
                # Assume key_data is correct and zuul may be offline
                args.glue["config_key_exists"] = True
            else:
                # This is the very first configuration,
                # we need to re-sync the config repo after zuul started
                args.glue["config_key_initialized"] = False

    def ensure_git_connection(self, name, args, host):
        """When no gerrit or github is connection is configured,
           make sure local git connections are defined"""
        git_connections = args.glue.setdefault("zuul_git_connections", [])
        for git_connection in git_connections:
            if git_connection["name"] == name:
                return
        if name == "local-cgit":
            baseurl = "http://%s/cgit" % host["hostname"]
        elif name == "opendev.org":
            baseurl = "https://opendev.org"
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
                for name, cnx in args.glue.get("resources_connections",
                                               {}).items():
                    if name == "__force_dict__":
                        continue
                    if args.glue["gateway_url"] in cnx["base-url"]:
                        conn_name = name
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
            sync_user = args.sfconfig['config-locations']['strategy']['user']
            zuul_config = args.sfconfig['zuul']
            for repo in ('config-repo', 'jobs-repo'):
                location = args.sfconfig['config-locations'].get(repo)
                if repo == 'config-repo':
                    # We only need url location of the config repo,
                    # it's needed for config-update job
                    url = location
                found = False
                # First we look for a matching github connections
                for conn in zuul_config.get('github_connections', []):
                    host = conn.get('hostname', 'github.com')
                    if host not in location:
                        continue
                    # Project name is the last two components
                    project_name = "/".join(location.split('/')[-2:])
                    if args.glue["sync_strategy"] != 'push':
                        _loc = location
                    else:
                        _loc = "ssh://%s@%s/%s" % (
                            sync_user, host, project_name)
                    if repo == "config-repo":
                        conn_name = conn["name"]
                        conf_name = project_name
                        conf_loc = _loc
                    elif conn_name != conn["name"]:
                        fail("Config and jobs needs to share "
                             "the same connection")
                    else:
                        jobs_name = project_name
                        jobs_loc = _loc
                    found = True
                    break

                if not found:
                    # If location is not matching github connections, look for
                    # available gerrit connections.
                    for conn in zuul_config.get('gerrit_connections', []):
                        puburl = conn.get('puburl')
                        if puburl not in location:
                            continue
                        # Project name is the remaining part after the puburl
                        project_name = location[len(puburl):].lstrip('/')
                        if args.glue["sync_strategy"] != 'push':
                            _loc = location
                        else:
                            _loc = "ssh://%s@%s/%s" % (
                                sync_user, conn["hostname"], project_name)
                        if repo == "config-repo":
                            conn_name = conn["name"]
                            conf_name = project_name
                            conf_loc = _loc
                        elif conn_name != conn["name"]:
                            fail("Config and jobs needs to share "
                                 "the same connection")
                        else:
                            jobs_name = project_name
                            jobs_loc = _loc
                        found = True
                        break

                if not found:
                    # If location is not matching gerrit connections, look for
                    # available pagure connections.
                    for conn in zuul_config.get('pagure_connections', []):
                        baseurl = conn.get('baseurl')
                        if not baseurl:
                            baseurl = 'https://%s' % conn.get(
                                'hostname', 'pagure.io')
                        if baseurl not in location:
                            continue
                        # Project name is the remaining part after the puburl
                        project_name = location[len(baseurl):].lstrip('/')
                        if args.glue["sync_strategy"] != 'push':
                            _loc = location
                        else:
                            _loc = "ssh://%s@%s/%s" % (
                                sync_user, conn["hostname"], project_name)
                        if repo == "config-repo":
                            conn_name = conn["name"]
                            conf_name = project_name
                            conf_loc = _loc
                        elif conn_name != conn["name"]:
                            fail("Config and jobs needs to share "
                                 "the same connection")
                        else:
                            jobs_name = project_name
                            jobs_loc = _loc
                        found = True
                        break

                if not found:
                    # If location is not matching github connections, look for
                    # available gitlab connections.
                    for conn in zuul_config.get('gitlab_connections', []):
                        baseurl = conn.get('baseurl')
                        if not baseurl:
                            baseurl = 'https://%s' % conn.get(
                                'hostname', 'gitlab.com')
                        if baseurl not in location:
                            continue
                        # Project name is the remaining part after the puburl
                        project_name = location[len(baseurl):].lstrip('/')
                        if args.glue["sync_strategy"] != 'push':
                            _loc = location
                        else:
                            _loc = "ssh://%s@%s/%s" % (
                                sync_user, conn["hostname"], project_name)
                        if repo == "config-repo":
                            conn_name = conn["name"]
                            conf_name = project_name
                            conf_loc = _loc
                        elif conn_name != conn["name"]:
                            fail("Config and jobs needs to share "
                                 "the same connection")
                        else:
                            jobs_name = project_name
                            jobs_loc = _loc
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
            zuul_name = "zuul/zuul-jobs"
            zuul_loc = "https://opendev.org/zuul/zuul-jobs"
            zuul_conn = None
            # Check if review.opendev.org is configured
            for connection in args.sfconfig.get("zuul", {}).get(
                    "gerrit_connections", []):
                if connection["hostname"] == "review.opendev.org":
                    zuul_conn = connection["name"]
                    break
            if not zuul_conn:
                # Check if git opendev.org is configured
                for connection in args.sfconfig.get("zuul", {}).get(
                        "git_connections", []):
                    if connection["baseurl"] == "https://opendev.org":
                        zuul_conn = connection["name"]
                        break
            if not zuul_conn:
                # Automatically adds git opendev.org connection
                zuul_conn = "opendev.org"
                self.ensure_git_connection(zuul_conn, args, host)
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

    def read_master_sf_resources(self, args, host):
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
                "%s/manage/v2/resources" %
                args.glue["master_sf_url"])
            self.master_resource = json.loads(req.read().decode('utf-8'))
            args.glue["resources_connections"] = self.master_resource.get(
                'resources', {}).get('connections', {})
            args.glue["resources_connections"]['__force_dict__'] = True
        except Exception:
            fail("Couldn't contact master-sf: %s" % (
                args.glue["master_sf_url"]))

        # Import master sf connection
        tenant_connections = set()
        tenant_conf = self.master_resource.get(
            "resources", {}).get("tenants", {}).get(
                args.glue["tenant_name"], {})
        tenant_def_conn = tenant_conf.get("default-connection")
        if tenant_def_conn:
            tenant_connections.add(tenant_def_conn)
        if tenant_conf.get("allowed-reporters"):
            tenant_connections.update(tenant_conf["allowed-reporters"])
        if tenant_conf.get("allowed-triggers"):
            tenant_connections.update(tenant_conf["allowed-triggers"])

        args.glue["zuul_gate"] = False

        for name, values in self.master_resource.get("resources", {}).get(
                "connections", {}).items():
            if name not in tenant_connections:
                continue
            if values.get("type") == "gerrit":
                hostname = parse.urlparse(
                    values.get("base-url")).hostname
                conn = {
                    "name": name,
                    "hostname": hostname,
                    "username": "zuul"
                }
                if name == tenant_def_conn:
                    # This is the connection of the tenant, use it for gate
                    args.glue["zuul_gate"] = True
                else:
                    # Otherwise, do not use it in the default pipelines
                    conn["default_pipelines"] = False
                args.sfconfig["zuul"]["gerrit_connections"].append(conn)

            elif values.get("type") == "github":
                conn = {
                    "name": name,
                    "app_name": values.get("github-app-name", ""),
                    "label_name": values.get("github-label", "")
                }
                if name == tenant_def_conn:
                    # This is the connection of the tenant, use it for gate
                    if values.get("github-app-name"):
                        args.glue["zuul_gate"] = True
                else:
                    # Otherwise, do not use it in the default pipelines
                    conn["default_pipelines"] = False
                args.sfconfig["zuul"]["github_connections"].append(conn)

            elif values.get("type") == "pagure":
                hostname = parse.urlparse(
                    values.get("base-url")).hostname
                conn = {
                    "name": name,
                    "hostname": hostname,
                }
                if name == tenant_def_conn:
                    # This is the connection of the tenant, use it for gate
                    args.glue["zuul_gate"] = True
                else:
                    # Otherwise, do not use it in the default pipelines
                    conn["default_pipelines"] = False
                args.sfconfig["zuul"]["pagure_connections"].append(conn)

    def resolve_tenant_informations(self, args, host):
        # TODO: make sfconfig.yaml zuul setting usable without sf-zuul role
        args.glue["zuul_default_retry_attempts"] = args.sfconfig[
            "zuul"].get("default_retry_attempts", 3)
        args.glue["zuul_periodic_pipeline_mail_rcpt"] = args.sfconfig[
            "zuul"]["periodic_pipeline_mail_rcpt"]

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
        if args.sfconfig["tenant-deployment"].get("zuul-jobs"):
            # Use the provided configuration
            zjc = args.sfconfig["tenant-deployment"].get("zuul-jobs")
            args.glue["zuul_jobs_connection_name"] = zjc["connection"]
            args.glue["zuul_jobs_project_name"] = zjc["project"]
            args.glue["zuul_upstream_zuul_jobs"] = True
        else:
            try:
                # TODO: add special attribute to zuul-jobs to better identify
                # it or add support for tenant custom zuul-jobs location...
                zj = self.master_resource.get(
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
        # Check if tenant config key already exists in master sf
        # If not then it means the tenant have not been defined yet on the
        # master sf. If yes, fetch it. The key will be used to initialize
        # Zuul's secrets (like logserver ssh key) into the tenant's sf
        # config repository.
        self.resolve_config_key(args,
                                "%s/zuul/api/tenant/%s/key/%s.pub" % (
                                    args.glue["master_sf_url"],
                                    args.glue["tenant_name"],
                                    args.glue["config_project_name"]))
        if not args.glue["config_key_exists"]:
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
