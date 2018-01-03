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


def update_sfconfig(args):
    """ This method ensure /etc/software-factory content is upgraded """
    dirty = False
    data = args.sfconfig

    if 'zuul' not in data:
        data['zuul'] = {
            'external_logservers': [],
            'default_log_site': "sflogs",
            'log_url': "",
        }
        dirty = True

    if 'static_nodes' not in data['zuul']:
        data['zuul']['static_nodes'] = []
        dirty = True

    if 'gerrit_connections' not in data['zuul']:
        data['zuul']['gerrit_connections'] = []
        dirty = True

    if "gerrit_connections" in data:
        for gerrit_connection in data["gerrit_connections"]:
            if not gerrit_connection["disabled"]:
                if 'disabled' in gerrit_connection:
                    del gerrit_connection['disabled']
                data['zuul']['gerrit_connections'].append(gerrit_connection)
        del data["gerrit_connections"]

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

    if "upstream_zuul_jobs" not in data.get("zuul3", {}):
        data.setdefault("zuul3", {})
        data["zuul3"]["upstream_zuul_jobs"] = False
        dirty = True

    if "default_nodeset_name" not in data["zuul3"]:
        data["zuul3"]["default_nodeset_name"] = "container"
        data["zuul3"]["default_nodeset_label"] = "centos-oci"
        dirty = True

    for github_connection in data['zuul3'].get('github_connections', []):
        if "app_key" not in github_connection:
            github_connection["app_key"] = None
            dirty = True

    for ci_service in ('zuul', 'zuul3'):
        if "periodic_pipeline_mail_rcpt" not in data[ci_service]:
            data[ci_service]['periodic_pipeline_mail_rcpt'] = "root@localhost"
            dirty = True

    args.save_sfconfig = dirty


def update_arch(args):
    dirty = False
    data = args.sfarch

    for host in data['inventory']:
        # Remove legacy roles
        if 'zuul' in host['roles']:
            host['roles'].remove('zuul')
            host['roles'].append('zuul-server')
            dirty = True
        if 'nodepool' in host['roles']:
            host['roles'].remove('nodepool')
            host['roles'].append('nodepool-launcher')
            dirty = True

    # Remove deployments related information
    for deploy_key in ("cpu", "mem", "hostid", "rolesname"):
        for host in data["inventory"]:
            if deploy_key in host:
                del host[deploy_key]
                dirty = True

    args.save_arch = dirty
