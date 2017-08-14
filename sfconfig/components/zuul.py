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
from sfconfig.utils import get_default


class ZuulServer(Component):
    role = "zuul-server"
    require_roles = ["mysql"]

    def configure(self):
        # ZuulV2 uses jenkins key
        self.get_or_generate_ssh_key("jenkins_rsa")
        # Also create zuul_rsa for managesf req
        self.get_or_generate_ssh_key("zuul_rsa")
        # When nodepool is disabled, disable offline_node when completed
        if ("nodepool" not in self.arch["roles"] or
            len(self.sfmain["nodepool"].get("providers", [])) == 0 or (
                len(self.sfmain["nodepool"]["providers"]) == 1 and
                not self.sfmain["nodepool"]["providers"][0]["auth_url"])):
            self.glue["zuul_offline_node_when_complete"] = False

        self.glue["zuul_pub_url"] = "%s/zuul/" % self.glue["gateway_url"]
        self.glue["zuul_internal_url"] = "http://%s:%s/" % (
            self.glue["zuul_server_host"], self.defaults["zuul_port"])
        self.glue["zuul_host"] = self.glue["zuul_server_host"]
        self.add_mysql_database("zuul")

        # Extra settings
        zuul_config = self.sfmain.get("zuul", {})
        for logserver in zuul_config.get("external_logserver", []):
            server = {
                "name": logserver["name"],
                "host": logserver.get("host", logserver["name"]),
                "user": logserver.get("user", "zuul"),
                "path": logserver["path"],
            }
            self.glue["logservers"].append(server)
        self.glue["zuul_log_url"] = get_default(
            zuul_config,
            "log_url",
            "%s/logs/{build.parameters[LOG_PATH]}" % self.glue["gateway_url"])
        self.glue["zuul_default_log_site"] = get_default(
            zuul_config, "default_log_site", "sflogs")
        self.glue["zuul_extra_gerrits"] = zuul_config.get("gerrit_connections",
                                                          [])

        # Zuul known hosts
        self.glue["zuul_ssh_known_hosts"] = []
        if "gerrit" in self.arch["roles"]:
            self.glue["zuul_ssh_known_hosts"].append({
                "host_packed": "[%s]:29418" % self.glue["gerrit_host"],
                "host": self.glue["gerrit_host"],
                "port": "29418",
            })
        for logserver in zuul_config.get("external_logserver", []):
            self.glue["zuul_ssh_known_hosts"].append({
                "host_packed": logserver.get("hostname", logserver["name"]),
                "host": logserver.get("hostname", logserver["name"]),
                "port": "22",
            })
        for extra_gerrit in self.glue.get("zuul_extra_gerrits", []):
            if extra_gerrit.get("port", 29418) == 22:
                host_packed = extra_gerrit["hostname"]
            else:
                host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                           extra_gerrit.get("port", 29418))
            self.glue["zuul_ssh_known_hosts"].append({
                "host_packed": host_packed,
                "host": extra_gerrit["hostname"],
                "port": extra_gerrit.get("port", 29418)
            })

        for static_node in self.glue.get("zuul_static_nodes", []):
            self.glue["zuul_ssh_known_hosts"].append({
                "host_packed": static_node.get("hostname"),
                "host": static_node.get("hostname"),
                "port": 22
            })


class ZuulMerger(Component):
    role = "zuul-merger"

    def argparse(self, parser):
        # TODO: document and use that new parameter
        parser.add_argument("--zuul-merger", action="append")


class ZuulLauncher(Component):
    role = "zuul-launcher"

    def configure(self):
        self.glue["jobs_zmq_publishers"].append(
            "tcp://%s:8888" % self.glue["zuul_launcher_host"])
        self.glue["loguser_authorized_keys"].append(
            self.glue["jenkins_rsa_pub"])
        self.glue["zuul_static_nodes"] = self.sfmain.get(
            'zuul', {}).get('static_nodes', [])


class NodepoolLauncher(Component):
    role = "nodepool-launcher"
    require_roles = ["zookeeper"]

    def prepare(self):
        super(NodepoolLauncher, self).prepare()
        self.glue["jobs_zmq_publishers"] = []

    def configure(self):
        self.glue["nodepool_providers"] = self.sfmain["nodepool"].get(
            "providers", [])
        self.glue["nodepool_host"] = self.glue["nodepool_launcher_host"]
        self.add_mysql_database("nodepool")
        if self.sfmain["network"]["disable_external_resources"]:
            self.glue["nodepool_disable_providers"] = True
