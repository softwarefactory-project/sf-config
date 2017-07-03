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

from sfconfig.utils import get_or_generate_ssh_key


def configure_server(args, host, sfconf, arch, glue, secrets, defaults):
    if ("nodepool" not in arch["roles"] or
        len(sfconf["nodepool"].get("providers", [])) == 0 or (
            len(sfconf["nodepool"]["providers"]) == 1 and
            not sfconf["nodepool"]["providers"][0]["auth_url"])):
        glue["zuul_offline_node_when_complete"] = False
    # Zuul2 is using jenkins ssh key
    glue.update(get_or_generate_ssh_key(args, "jenkins_rsa"))
    glue["zuul_pub_url"] = "%s/zuul/" % glue["gateway_url"]
    glue["zuul_internal_url"] = "http://%s:%s/" % (
        host["hostname"], defaults["zuul_port"])
    glue["zuul_mysql_host"] = glue["mysql_host"]
    glue["mysql_databases"]["zuul"] = {
        'hosts': list(set(('localhost',
                           host['hostname'],
                           glue['managesf_host']))),
        'user': 'zuul',
        'password': secrets['zuul_mysql_password'],
    }
    # Extra zuul settings
    zuul_config = sfconf.get("zuul", {})
    for logserver in zuul_config.get("external_logserver", []):
        server = {
            "name": logserver["name"],
            "host": logserver.get("host", logserver["name"]),
            "user": logserver.get("user", "zuul"),
            "path": logserver["path"],
        }
        glue["logservers"].append(server)
    glue["zuul_log_url"] = zuul_config.get(
        "log_url",
        "%s/logs/{build.parameters[LOG_PATH]}" % glue["gateway_url"])
    glue["zuul_default_log_site"] = zuul_config.get("default_log_site",
                                                    "sflogs")
    glue["zuul_extra_gerrits"] = zuul_config.get("gerrit_connections", [])

    # Zuul known hosts
    glue["zuul_ssh_known_hosts"] = []
    if "gerrit" in arch["roles"]:
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": "[%s]:29418" % glue["gerrit_host"],
                "host": glue["gerrit_host"],
                "port": "29418",
            }
        )
    for extra_gerrit in glue.get("zuul_extra_gerrits", []):
        if extra_gerrit.get("port", 29418) == 22:
            host_packed = extra_gerrit["hostname"]
        else:
            host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                       extra_gerrit.get("port", 29418))
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": host_packed,
                "host": extra_gerrit["hostname"],
                "port": extra_gerrit.get("port", 29418)
            }
        )


def configure_launcher(args, host, sfconf, arch, glue, secrets, defaults):
    glue["zuul_launcher_host"] = host["hostname"]
    glue["jobs_zmq_publishers"].append(
        "tcp://%s:8888" % glue["zuul_launcher_host"])
    glue["loguser_authorized_keys"].append(glue["jenkins_rsa_pub"])
