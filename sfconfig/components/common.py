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


def get_sf_version():
    try:
        return open("/etc/sf-release").read().strip()
    except IOError:
        return "master"


def get_previous_version():
    try:
        return open("/var/lib/software-factory/.version").read().strip()
    except IOError:
        return "2.5.0"


class InstallServer(Component):
    role = "install-server"

    def configure(self, args, host):
        self.get_or_generate_ssh_key(args, "service_rsa")

        args.glue["sf_version"] = get_sf_version()
        args.glue["sf_previous_version"] = get_previous_version()


class Managesf(Component):
    role = "managesf"

    def configure(self, args, host):
        self.add_mysql_database(args, "managesf")
        args.glue["managesf_internal_url"] = "http://%s:%s" % (
            args.glue["managesf_host"], args.defaults["managesf_port"])


class Jenkins(Component):
    role = "jenkins"
    require_roles = ["nodepool-launcher"]

    def configure(self, args, host):
        self.get_or_generate_ssh_key(args, "jenkins_rsa")
        args.glue["jenkins_internal_url"] = "http://%s:%s/jenkins/" % (
            args.glue["jenkins_host"], args.defaults["jenkins_http_port"])
        args.glue["jenkins_api_url"] = "http://%s:%s/jenkins/" % (
            args.glue["jenkins_host"], args.defaults["jenkins_api_port"])
        args.glue["jenkins_pub_url"] = "%s/jenkins/" % args.glue["gateway_url"]
        args.glue["jobs_zmq_publishers"].append(
            "tcp://%s:8889" % args.glue["jenkins_host"])


class LogServer(Component):
    role = "logserver"

    def prepare(self, args):
        super(LogServer, self).prepare(args)
        args.glue["loguser_authorized_keys"] = []
        args.glue["logservers"] = []

    def configure(self, args, host):
        args.glue["logservers"].append({
            "name": "sflogs",
            "host": args.glue["logserver_host"],
            "user": "loguser",
            "path": "/var/www/logs",
        })
        if args.glue["logserver_host"] != args.glue["install_server_host"]:
            args.glue["zuul_ssh_known_hosts"].append({
                "host_packed": args.glue["logserver_host"],
                "host": args.glue["logserver_host"],
                "port": 22
            })


class Pages(Component):
    role = "pages"

    def configure(self, args, host):
        args.glue["pages"] = {
            "name": "pages",
            "host": args.glue["pages_host"],
            "user": "pagesuser",
            "path": "/var/www/html/pages",
        }
        args.glue["pagesuser_authorized_keys"] = []
        if "zuul-launcher" in args.glue["roles"]:
            args.glue["pagesuser_authorized_keys"].append(
                args.glue["jenkins_rsa_pub"])
        if "zuul3-executor" in args.glue["roles"]:
            args.glue["pagesuser_authorized_keys"].append(
                args.glue["zuul_rsa_pub"])


class Grafana(Component):
    role = "grafana"

    def configure(self, args, host):
        args.glue["grafana_internal_url"] = "http://%s:%s" % (
            args.glue["grafana_host"], args.defaults["grafana_http_port"])
        self.add_mysql_database(args, "grafana")


class Lodgeit(Component):
    role = "lodgeit"

    def configure(self, args, host):
        self.add_mysql_database(args, "lodgeit")


class Etherpad(Component):
    role = "etherpad"

    def configure(self, args, host):
        self.add_mysql_database(args, "etherpad")


class Storyboard(Component):
    role = "storyboard"
    require_roles = ["rabbitmq"]

    def configure(self, args, host):
        self.add_mysql_database(args, "storyboard")
        args.glue["storyboard_internal_url"] = "http://%s:%s/v1/" % (
            args.glue["storyboard_host"],
            args.defaults["storyboard_http_port"])


class Mumur(Component):
    role = "murmur"

    def configure(self, args, host):
        if args.sfconfig["mumble"].get("password"):
            args.glue["murmur_password"] = args.sfconfig["mumble"].get(
                "password")


class ElasticSearch(Component):
    role = "elasticsearch"

    def configure(self, args, host):
        if 'heap_size' in args.sfconfig['elasticsearch']:
            args.glue['elasticsearch_heap_size'] = args.sfconfig[
                'elasticsearch']['heap_size']
        if 'replicas' in args.sfconfig['elasticsearch']:
            args.glue['elasticsearch_replicas'] = args.sfconfig[
                'elasticsearch']['replicas']


class LogStash(Component):
    role = "logstash"

    def configure(self, args, host):
        if 'retention_days' in args.sfconfig['logstash']:
            args.glue['logstash_retention_days'] = \
                args.sfconfig['logstash']['retention_days']
