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


class Zuul3Scheduler(Component):
    role = "zuul3-scheduler"
    require_role = ["nodepool3", "zookeeper"]

    def configure(self, args, host):
        args.glue["zuul3_host"] = args.glue["zuul3_scheduler_host"]
        self.add_mysql_database(args, "zuul3")
        self.get_or_generate_ssh_key(args, "zuul_rsa")
        self.get_or_generate_ssh_key(args, "zuul_logserver_rsa")
        args.glue["zuul3_pub_url"] = "%s/zuul3/" % args.glue["gateway_url"]
        args.glue["zuul3_internal_url"] = "http://%s:%s/" % (
            args.glue["zuul3_host"], args.defaults["zuul3_port"])
        args.glue["zuul3_mysql_host"] = args.glue["mysql_host"]
        args.glue["loguser_authorized_keys"].append(
            args.glue["zuul_logserver_rsa_pub"])

        # Extra settings
        zuul3_config = args.sfconfig.get("zuul3", {})
        args.glue["zuul3_extra_gerrits"] = zuul3_config.get(
            "gerrit_connections", [])
        args.glue["zuul3_success_log_url"] = get_default(
            zuul3_config, "success_log_url",
            "%s/logs/{build.uuid}/" % args.glue["gateway_url"]
        )
        args.glue["zuul3_failure_log_url"] = get_default(
            zuul3_config, "failure_log_url",
            "%s/logs/{build.uuid}/" % args.glue["gateway_url"]
        )
        args.glue["zuul3_ssh_known_hosts"] = []
        args.glue["zuul3_github_connections"] = []
        if "gerrit" in args.glue["roles"]:
            args.glue["zuul3_ssh_known_hosts"].append({
                "host_packed": "[%s]:29418" % args.glue["gerrit_host"],
                "host": args.glue["gerrit_host"],
                "port": "29418",
            })
        for extra_gerrit in args.glue.get("zuul3_extra_gerrits", []):
            if extra_gerrit.get("port", 29418) == 22:
                host_packed = extra_gerrit["hostname"]
            else:
                host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                           extra_gerrit.get("port", 29418))
            args.glue["zuul3_ssh_known_hosts"].append({
                "host_packed": host_packed,
                "host": extra_gerrit["hostname"],
                "port": extra_gerrit.get("port", 29418)
            })
        if "logserver" in args.glue["roles"]:
            args.glue["zuul3_ssh_known_hosts"].append({
                "host_packed": args.glue["logserver_host"],
                "host": args.glue["logserver_host"],
                "port": 22
            })
        for github_connection in zuul3_config.get("github_connections", []):
            if github_connection.get("port", 22) == 22:
                host_packed = github_connection.get("hostname", "github.com")
            else:
                host_packed = "[%s]:%s" % (github_connection["hostname"],
                                           github_connection["port"])
            args.glue["zuul3_ssh_known_hosts"].append({
                "host_packed": host_packed,
                "host": github_connection.get("hostname", "github.com"),
                "port": github_connection.get("port", 22)
            })
            args.glue["zuul3_github_connections"].append(github_connection)


class Zuul3Web(Component):
    role = "zuul3-web"
    require_role = ["zuul3-scheduler"]

    def configure(self, args, host):
        args.glue["zuul3_web_url"] = "%s:%s" % (
            args.glue["zuul3_web_host"], args.defaults["zuul3_web_port"])
