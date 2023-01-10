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

import os
import sys
import time
import uuid
import re
from sfconfig.utils import pread


def get_version():
    try:
        sf_version = open("/etc/sf-release").read().strip()
    except IOError:
        sf_version = "master"
    return sf_version


def update_sfconfig(args):
    """ This method ensure /etc/software-factory content is upgraded """
    dirty = False
    data = args.sfconfig

    sf_version = get_version()
    has_kc = (sf_version == 'master' or sf_version >= '3.8')

    # 3.7.0: add external_authenticators config field
    if 'zuul' in data:
        if 'external_authenticators' not in data['zuul']:
            data['zuul']['external_authenticators'] = []
            dirty = True

    # 2.6.0: expose elasticsearch config
    # 3.3.0: update elasticsearch config
    # 3.6.0: update elasticsearch config
    # 3.8.0  change role name from elasticsearch to opensearch
    if 'opensearch' not in data:
        data['opensearch'] = data.get('elasticsearch', {})
        dirty = True
    if 'replicas' not in data['opensearch']:
        data['opensearch']['replicas'] = 0
        dirty = True
    if 'heap_size' in data['opensearch']:
        del data['opensearch']['heap_size']
        dirty = True
    if 'maximum_heap_size' not in data['opensearch']:
        data['opensearch']['maximum_heap_size'] = '512m'
        dirty = True
    if 'minimum_heap_size' not in data['opensearch']:
        data['opensearch']['minimum_heap_size'] = '128m'
        dirty = True

    if 'opensearch_dashboards' not in data:
        data['opensearch_dashboards'] = data.get('kibana', {})
        dirty = True

    if 'kibana' in data:
        del data['kibana']
        dirty = True

    if 'external_opensearch' not in data:
        data['external_opensearch'] = data.get('external_elasticsearch', {})
        dirty = True

    if 'external_elasticsearch' in data:
        del data['external_elasticsearch']
        dirty = True

    if 'logstash' in data:
        data.pop('logstash')

    if 'disable_external_resources' not in data['network']:
        data['network']['disable_external_resources'] = False
        dirty = True
    if args.disable_external_resources and \
       not data['network']['disable_external_resources']:
        data['network']['disable_external_resources'] = True
        dirty = True

    # 3.3.0: update gateway_directories default value
    if data.get('gateway_directories', '') == '':
        data['gateway_directories'] = []
        dirty = True

    # 2.7.0: remove useless backup config section
    if 'backup' in data:
        del data['backup']
        dirty = True

    # 3.0: rename (zuul|nodepool)3 without suffix
    for key in ('zuul', 'nodepool'):
        if '%s3' % key in data:
            data[key] = data['%s3' % key]
            del data['%s3' % key]
            dirty = True

    # 2.7: refactor logs settings
    for key in ("disabled", "container", "logserver_prefix", "authurl",
                "x_storage_url", "username", "password", "tenantname",
                "authversion", "x_tempurl_key", "send_tempurl_key"):
        if "swift_logsexport_%s" % key in data['logs']:
            key = "swift_logsexport_%s" % key
        if key in data['logs']:
            del data['logs'][key]
            dirty = True

    if "expiry" not in data["logs"]:
        data["logs"]["expiry"] = 60
        dirty = True

    if "upstream_zuul_jobs" not in data.get("zuul", {}):
        data.setdefault("zuul", {})
        data["zuul"]["upstream_zuul_jobs"] = False
        dirty = True

    if "default_nodeset_name" not in data["zuul"]:
        data["zuul"]["default_nodeset_name"] = "container"
        data["zuul"]["default_nodeset_label"] = "centos-oci"
        dirty = True

    for github_connection in data['zuul'].get('github_connections', []):
        if "app_key" not in github_connection:
            github_connection["app_key"] = None
            dirty = True

    if "periodic_pipeline_mail_rcpt" not in data['zuul']:
        data['zuul']['periodic_pipeline_mail_rcpt'] = "root@localhost"
        dirty = True

    if "prerelease_regexp" not in data['zuul']:
        data['zuul']['prerelease_regexp'] = r'([0-9]+)\.([0-9]+)\.([0-9]+)' \
             r'(?:-([0-9alpha|beta|rc.-]+))?(?:\+([0-9a-zA-Z.-]+))?'
        dirty = True

    if "release_regexp" not in data['zuul']:
        data['zuul']['release_regexp'] = r'([0-9]+)\.([0-9]+)\.([0-9]+)' \
            r'(?:-([0-9a-zA-Z.-]+))?(?:\+([0-9a-zA-Z.-]+))?'
        dirty = True

    if not has_kc and "active_directory" not in data["authentication"]:
        data["authentication"]["active_directory"] = {
            "disabled": True,
            "ldap_url": "ldap://sftests.com",
            "ldap_account_domain": "domain.sftests.com",
            "ldap_account_base": "ou=Users,dc=domain,dc=sftests,dc=com",
            "ldap_account_username_attribute": "sAMAccountName",
            "ldap_account_mail_attribute": "mail",
            "ldap_account_surname_attribute": "name",
        }
        dirty = True

    if "default_retry_attempts" not in data['zuul']:
        data['zuul']['default_retry_attempts'] = 3
        dirty = True

    # Check for duplicate gerrit connection bug
    to_delete = None
    for connection in data.get("zuul", {}).get("gerrit_connections", []):
        if connection["name"] == "gerrit":
            print("Warning: Gerrit connection named 'gerrit' is reserved for "
                  "the internal gerrit")
            to_delete = connection
    if to_delete:
        data["zuul"]["gerrit_connections"].remove(to_delete)
        dirty = True

    # Check for duplicate external_authenticators
    ext_auth = []
    for auth in data.get("zuul", {}).get("external_authenticators", []):
        if auth['name'] in ext_auth:
            print("Warning: There is duplication in Zuul "
                  "external_authenticators.")
            data['zuul']['external_authenticators'].remove(auth)
            dirty = True
        else:
            ext_auth.append(auth['name'])

    if 'allowed_proxy_prefixes' in data['authentication']:
        del data['authentication']['allowed_proxy_prefixes']
        dirty = True

    if "git_connections" not in data["zuul"]:
        data["zuul"]["git_connections"] = []
        dirty = True

    for elk in data['zuul'].get("opensearch_connections", []):
        if elk["name"] == "opensearch":
            print("Warning: Elasticsearch connection named 'opensearch' "
                  "is reserved for the internal elasticsearch service")
            exit(1)

    if 'opensearch_connections' not in data['zuul']:
        data['zuul']['opensearch_connections'] = \
                data['zuul'].pop('elasticsearch_connections', {})
        dirty = True

    # 3.3: add SAML2 groups values
    if not has_kc:
        if 'SAML2' in data['authentication']:
            if 'groups' not in data['authentication']['SAML2']['mapping']:
                data['authentication']['SAML2']['mapping']['groups'] = None
                dirty = True

        # 3.1: add SAML2 default auth values
        else:
            data['authentication']['SAML2'] = {
                'disabled': True,
                'login_button_text': 'Replace me with a SAML login prompt',
                'key_delimiter': ';',
                'mapping': {
                    'login': 'urn:oid:2.5.4.42',
                    'email': 'urn:oid:1.2.840.113549.1.9.1',
                    'name': 'urn:oid:2.5.4.42',
                    'uid': 'uid',
                    'ssh_keys': None,
                    'groups': None,
                },
            }
            dirty = True

    if "config-locations" not in data:
        data["config-locations"] = {
            'config-repo': '', 'jobs-repo': '',
            'strategy': {'sync': 'push', 'user': 'git'}}
        dirty = True

    if "tenant-deployment" not in data:
        data["tenant-deployment"] = {}
        dirty = True

    if "clouds_file" not in data["nodepool"]:
        data["nodepool"]["clouds_file"] = None
        dirty = True

    if "kube_file" not in data["nodepool"]:
        data["nodepool"]["kube_file"] = None
        dirty = True

    if "aws_file" not in data["nodepool"]:
        data["nodepool"]["aws_file"] = None
        dirty = True

    if "default-tenant-name" not in data:
        data["default-tenant-name"] = "local"
        dirty = True

    if "tls_cert_file" not in data["network"]:
        data["network"]["tls_cert_file"] = ""
        data["network"]["tls_chain_file"] = ""
        data["network"]["tls_key_file"] = ""
        dirty = True

    if "ara_report" not in data["zuul"]:
        data["zuul"]["ara_report"] = True
        dirty = True

    if "gerrit" not in data:
        data["gerrit"] = {
            "all_projects_config": [{
                'name': 'plugin.reviewers-by-blame.maxReviewers',
                'value': '5'
            }, {
                'name': 'plugin.reviewers-by-blame.ignoreDrafts',
                'value': 'true'
            }, {
                'name': 'plugin.reviewers-by-blame.ignoreSubjectRegEx',
                'value': "'(WIP|DNM)(.*)'"
            }]
        }
        dirty = True

    if 'elasticsearch' in data:
        data.pop('elasticsearch')
        dirty = True

    if 'kibana' in data:
        data.pop('kibana')
        dirty = True

    args.save_sfconfig = dirty

    if data['authentication']['admin_password'] == 'CHANGE_ME' or \
       data['authentication']['admin_password'] == 'userpass':
        new_pass = uuid.uuid4().hex
        data['authentication']['admin_password'] = new_pass
        # Admin_password is changed in place to avoid automatic sfconfig.yaml
        # upgrade on first deployment (which break formating)
        raw_config = open(args.config).read()
        open(args.config, 'w').write(re.sub(
            "admin_password:.*", "admin_password: %s" % new_pass, raw_config))

    # 3.8 - Keycloak related stuff
    keycloak_warning = ""
    gh_break = False
    oauth2 = data["authentication"].get('oauth2')

    if "sso_cookie_timeout" in data["authentication"]:
        data["authentication"]["sso_session_timeout"] = (
            data["authentication"]["sso_cookie_timeout"]
        )
        del data["authentication"]["sso_cookie_timeout"]
    if "ldap" in data["authentication"]:
        keycloak_warning += ("- Found entry in 'authentication.ldap': ")
        keycloak_warning += ("LDAP authentication must be "
                             "configured in Keycloak directly.\n")
    if "active_directory" in data["authentication"]:
        keycloak_warning += (
            "- Found entry in 'authentication.active_directory': ")
        keycloak_warning += ("Active Directory authentication must "
                             "be configured in Keycloak directly.\n")
    if "github" in oauth2:
        if not oauth2["github"].get("disabled", True):
            gh_break = True
        if oauth2["github"].get('github_allowed_organizations', []) != []:
            keycloak_warning += (
                "- Found entry in 'authentication.oauth2.github': ")
            keycloak_warning += ("Github organization filtering is "
                                 "not supported anymore.\n")
    if "google" in oauth2:
        keycloak_warning += (
            "- Found entry in 'authentication.oauth2.google': ")
        keycloak_warning += ("Google authentication must be configured "
                             "as a social provider in Keycloak directly.\n")
    if "bitbucket" in oauth2:
        keycloak_warning += (
            "- Found entry in 'authentication.oauth2.bitbucket': ")
        keycloak_warning += ("Bitbucket authentication must be "
                             "configured as a social provider in Keycloak "
                             "directly.\n")
    if "openid" in data["authentication"]:
        keycloak_warning += (
            "- Found entry in 'authentication.openid': ")
        keycloak_warning += ("Generic OpenID authentication must be "
                             "configured in Keycloak directly.\n")
    if "openid_connect" in data["authentication"]:
        keycloak_warning += (
            "- Found entry in 'authentication.openid_connect': ")
        keycloak_warning += ("OpenID Connect authentication must be "
                             "configured in Keycloak directly.\n")
    if "SAML2" in data["authentication"]:
        keycloak_warning += (
            "- Found entry in 'authentication.SAML2': ")
        keycloak_warning += ("SAML2 authentication must be configured "
                             "in Keycloak directly.\n")
    if len(keycloak_warning) > 0:
        print("The following authentication settings are obsolete. "
              "You can remove them from the configuration file "
              "at any time, they will be safely ignored by sf-config:\n\n")
        print(keycloak_warning)
    if gh_break:
        fqdn = args.sfconfig.get('fqdn', "{FQDN}")
        print("""
#####################################################
#                      WARNING                      #
#####################################################

(The program will pause for a few seconds, resume by hitting
Ctrl+c)

Github is configured as a third-party authenticator.
You need to get on the Github OAuth application settings page
(https://github.com/settings/developers  then "OAuth Apps")
to update the authorization callback URL to the following
new value:

https://%s/auth/realms/SF/broker/github/endpoint

""" % fqdn)
        try:
            for remaining in range(20, 0, -1):
                sys.stdout.write("\r")
                sys.stdout.write(
                    "{:2d} seconds until resuming.".format(remaining)
                )
                sys.stdout.flush()
                time.sleep(1)
            print("\rResuming upgrade.")
        except KeyboardInterrupt:
            sys.stdout.flush()
            print("\rCountdown interrupted, resuming upgrade.")


def runc_provider_exists():
    runc = ''
    if os.path.isdir("/root/config/nodepool"):
        runc = pread(["grep", "-r", "driver: runc", "/root/config/nodepool"])
        if runc:
            print("Existing runc provider:\n" + runc)
    return runc != ''


def update_arch(args):
    dirty = False
    data = args.sfarch

    sf_version = get_version()

    for host in data['inventory']:
        if "hypervisor-oci" in host["roles"] or \
           "hypervisor-runc" in host["roles"] or \
           runc_provider_exists():
            print("Runc providers needs to be removed manually "
                  "before performing the upgrade.")
            exit(1)

        # Remove legacy roles
        if 'pages' in host['roles']:
            host['roles'].remove('pages')
        for removed in (
                'zuul-server', 'zuul-merger', 'zuul-launcher',
                'nodepool-launcher', 'nodepool-builder',
                'jenkins'):
            if sf_version == "2.7" and removed in host['roles']:
                print("Please disable the role %s"
                      " from the architecure file before running"
                      " again this command." % removed)
                sys.exit(-1)
        for idx in range(len(host['roles'])):
            if host['roles'][idx].startswith('zuul3-'):
                host['roles'][idx] = host['roles'][idx].replace('zuul3',
                                                                'zuul')
                dirty = True
            if host['roles'][idx].startswith('nodepool3-'):
                host['roles'][idx] = host['roles'][idx].replace('nodepool3',
                                                                'nodepool')
                dirty = True
            if host['roles'][idx].startswith('job-logs-gearman-client'):
                host['roles'][idx] = host['roles'][idx].replace(
                    'job-logs-gearman-client', 'log-processing')
                dirty = True
            if host['roles'][idx].startswith('job-logs-gearman-worker'):
                host['roles'][idx] = host['roles'][idx].replace(
                    'job-logs-gearman-worker', '')
                dirty = True
            if host['roles'][idx].startswith('logstash'):
                host['roles'][idx] = host['roles'][idx].replace(
                    'logstash', '')
                dirty = True

        # Filter for empty roles
        host['roles'] = [r for r in host['roles'] if r]

        # Remove storyboard
        for sb in ("rabbitmq", "storyboard", "storyboard-webclient"):
            if sb in host['roles']:
                host['roles'].remove(sb)

        if sf_version > "3.7":
            print("Keycloak replaces Cauth starting from release 3.8. "
                  "The arch file will be modified accordingly.")
            host['roles'] = [r.replace('cauth', 'keycloak')
                             for r in host['roles']]

    # Remove deployments related information
    for deploy_key in ("cpu", "mem", "hostid", "rolesname"):
        for host in data["inventory"]:
            if deploy_key in host:
                del host[deploy_key]
                dirty = True

    args.save_arch = dirty
