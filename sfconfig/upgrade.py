# Copyright (C) 2017 Red Hat
#
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


def update_sfconfig(data):
    """ This method ensure /etc/software-factory content is upgraded """
    dirty = False

    # Remove it after 2.6.0 upgrade
    if 'welcome_page_path' not in data:
        data['welcome_page_path'] = 'sf/welcome.html'
        dirty = True

    # 2.6.0: add scp backup parameters
    if 'method' not in data['backup']:
        data['backup']['method'] = 'swift'
        data['backup']['scp_backup_host'] = 'remoteserver.sftests.com'
        data['backup']['scp_backup_port'] = 22
        data['backup']['scp_backup_user'] = 'root'
        data['backup']['scp_backup_directory'] = '/var/lib/remote_backup'
        data['backup']['scp_backup_max_retention_secs'] = 864000
        dirty = True

    if 'zuul' not in data:
        data['zuul'] = {
            'external_logservers': [],
            'default_log_site': "sflogs",
            'log_url': "",
        }
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
        dirty = True

    return dirty


def clean_arch(data):
    dirty = False
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
    # Remove data added *IN-PLACE* by utils_refarch
    # Those are now saved in _arch.yaml instead
    for dynamic_key in ("domain", "gateway", "gateway_ip", "install",
                        "install_ip", "ip_prefix", "roles", "hosts_file"):
        if dynamic_key in data:
            del data[dynamic_key]
            dirty = True

    # Remove deployments related information
    for deploy_key in ("cpu", "disk", "mem", "hostid", "rolesname",
                       "hostname"):
        for host in data["inventory"]:
            if deploy_key in host:
                del host[deploy_key]
                dirty = True
    return dirty
