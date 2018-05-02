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

import sys
import uuid
import re


def update_sfconfig(args):
    """ This method ensure /etc/software-factory content is upgraded """
    dirty = False
    data = args.sfconfig

    # 2.6.0: expose elasticsearch config
    if 'elasticsearch' not in data:
        data['elasticsearch'] = {}
        dirty = True
    if 'heap_size' not in data['elasticsearch']:
        data['elasticsearch']['heap_size'] = '512m'
        dirty = True
    if 'replicas' not in data['elasticsearch']:
        data['elasticsearch']['replicas'] = 0
        dirty = True

    # 2.6.0: expose logstash config
    if 'logstash' not in data:
        data['logstash'] = {}
        dirty = True
    if 'retention_days' not in data['logstash']:
        data['logstash']['retention_days'] = 60

    if 'disable_external_resources' not in data['network']:
        data['network']['disable_external_resources'] = False
        dirty = True

    if data['network']['disable_external_resources'] != \
       args.disable_external_resources:
        data['network']['disable_external_resources'] = \
            args.disable_external_resources
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

    if "active_directory" not in data["authentication"]:
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
    for connection in data["zuul"].get("gerrit_connections", []):
        if connection["name"] == "gerrit":
            print("Warning: Gerrit connection named 'gerrit' is reserved for "
                  "the internal gerrit")
            to_delete = connection
    if to_delete:
        data["zuul"]["gerrit_connections"].remove(to_delete)
        dirty = True

    if 'allowed_proxy_prefixes' in data['authentication']:
        del data['authentication']['allowed_proxy_prefixes']
        dirty = True

    if "git_connections" not in data["zuul"]:
        data["zuul"]["git_connections"] = []
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

    if args.fqdn and args.fqdn != data['fqdn']:
        data['fqdn'] = args.fqdn
        open(args.config, 'w').write(re.sub(
            "^fqdn:.*", "fqdn: %s" % args.fqdn, open(args.config).read()))


def update_arch(args):
    dirty = False
    data = args.sfarch

    try:
        sf_version = open("/etc/sf-release").read().strip()
    except IOError:
        sf_version = "master"

    for host in data['inventory']:
        # Set remote flag
        if host['roles'] == ["hypervisor-oci"]:
            if not host.get('remote'):
                host['remote'] = True
                dirty = True
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

    # Remove deployments related information
    for deploy_key in ("cpu", "mem", "hostid", "rolesname"):
        for host in data["inventory"]:
            if deploy_key in host:
                del host[deploy_key]
                dirty = True

    args.save_arch = dirty
