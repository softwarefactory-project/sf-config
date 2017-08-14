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


class InstallServer(Component):
    role = "install-server"

    def configure(self):
        self.get_or_generate_ssh_key("service_rsa")


class Managesf(Component):
    role = "managesf"

    def configure(self):
        self.add_mysql_database("managesf")
        self.glue["managesf_internal_url"] = "http://%s:%s" % (
            self.glue["managesf_host"], self.defaults["managesf_port"])


class Jenkins(Component):
    role = "jenkins"
    require_roles = ["nodepool-launcher"]

    def configure(self):
        self.get_or_generate_ssh_key("jenkins_rsa")
        self.glue["jenkins_internal_url"] = "http://%s:%s/jenkins/" % (
            self.glue["jenkins_host"], self.defaults["jenkins_http_port"])
        self.glue["jenkins_api_url"] = "http://%s:%s/jenkins/" % (
            self.glue["jenkins_host"], self.defaults["jenkins_api_port"])
        self.glue["jenkins_pub_url"] = "%s/jenkins/" % self.glue["gateway_url"]
        self.glue["jobs_zmq_publishers"].append(
            "tcp://%s:8889" % self.glue["jenkins_host"])


class LogServer(Component):
    role = "logserver"

    def prepare(self):
        super(LogServer, self).prepare()
        self.glue["loguser_authorized_keys"] = []
        self.glue["logservers"] = []

    def configure(self):
        self.glue["logservers"].append({
            "name": "sflogs",
            "host": self.glue["logserver_host"],
            "user": "loguser",
            "path": "/var/www/logs",
        })
        if self.glue["logserver_host"] != self.glue["install_server_host"]:
            self.glue["zuul_ssh_known_hosts"].append({
                "host_packed": self.glue["logserver_host"],
                "host": self.glue["logserver_host"],
                "port": 22
            })


class Pages(Component):
    role = "pages"

    def configure(self):
        self.glue["pages"] = {
            "name": "pages",
            "host": self.glue["pages_host"],
            "user": "pagesuser",
            "path": "/var/www/html/pages",
        }
        self.glue["pagesuser_authorized_keys"] = []
        if "zuul-launcher" in self.arch["roles"]:
            self.glue["pagesuser_authorized_keys"].append(
                self.glue["jenkins_rsa_pub"])
        if "zuul3-executor" in self.arch["roles"]:
            self.glue["pagesuser_authorized_keys"].append(
                self.glue["zuul_rsa_pub"])


class Grafana(Component):
    role = "grafana"

    def configure(self):
        self.glue["grafana_internal_url"] = "http://%s:%s" % (
            self.glue["grafana_host"], self.defaults["grafana_http_port"])
        self.add_mysql_database("grafana")


class Lodgeit(Component):
    role = "lodgeit"
    require_roles = ["mysql"]

    def configure(self):
        self.add_mysql_database("lodgeit")


class Etherpad(Component):
    role = "etherpad"

    def configure(self):
        self.add_mysql_database("etherpad")


class Storyboard(Component):
    role = "storyboard"
    require_roles = ["rabbitmq"]

    def configure(self):
        self.add_mysql_database("storyboard")
        self.glue["storyboard_internal_url"] = "http://%s:%s/v1/" % (
            self.glue["storyboard_host"],
            self.defaults["storyboard_http_port"])


class Mumur(Component):
    role = "murmur"

    def configure(self):
        if self.sfmain["mumble"].get("password"):
            self.glue["murmur_password"] = self.sfmain["mumble"].get(
                "password")


class ElasticSearch(Component):
    role = "elasticsearch"

    def configure(self):
        if 'heap_size' in self.sfmain['elasticsearch']:
            self.glue['elasticsearch_heap_size'] = self.sfmain[
                'elasticsearch']['heap_size']
        if 'replicas' in self.sfmain['elasticsearch']:
            self.glue['elasticsearch_replicas'] = self.sfmain[
                'elasticsearch']['replicas']


class LogStash(Component):
    role = "logstash"

    def configure(self):
        if 'retention_days' in self.sfmain['logstash']:
            self.glue['logstash_retention_days'] = \
                self.sfmain['logstash']['retention_days']
