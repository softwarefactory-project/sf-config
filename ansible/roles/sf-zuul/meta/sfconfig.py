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

    def usage(self, parser):
        parser.add_argument("--zuul-ssh-key", metavar="KEY_PATH",
                            help="Use existing ssh key for zuul")

    def argparse(self, args):
        if args.zuul_ssh_key:
            self.import_ssh_key(args, "jenkins_rsa", args.zuul_ssh_key)

    def configure(self, args, host):
        # ZuulV2 uses jenkins key
        self.get_or_generate_ssh_key(args, "jenkins_rsa")
        # Add sqlreporter database
        args.glue["zuul_host"] = args.glue["zuul_server_host"]
        self.add_mysql_database(args, "zuul")
        # When nodepool is disabled, disable offline_node when completed
        if ("nodepool" not in args.glue["roles"] or
            len(args.sfconfig["nodepool"].get("providers", [])) == 0 or (
                len(args.sfconfig["nodepool"]["providers"]) == 1 and
                not args.sfconfig["nodepool"]["providers"][0]["auth_url"])):
            args.glue["zuul_offline_node_when_complete"] = False

        args.glue["zuul_pub_url"] = "%s/zuul/" % args.glue["gateway_url"]
        args.glue["zuul_internal_url"] = "http://%s:%s/" % (
            args.glue["zuul_server_host"], args.defaults["zuul_port"])

        args.glue["zuul_periodic_pipeline_mail_rcpt"] = args.sfconfig[
            "zuul"]["periodic_pipeline_mail_rcpt"]

        # Extra settings
        zuul_config = args.sfconfig.get("zuul", {})
        for logserver in zuul_config.get("external_logservers", []):
            server = {
                "name": logserver["name"],
                "host": logserver.get("host", logserver["name"]),
                "user": logserver.get("user", "zuul"),
                "path": logserver["path"],
            }
            args.glue["logservers"].append(server)
        args.glue["zuul_log_url"] = get_default(
            zuul_config,
            "log_url",
            "%s/logs/{build.parameters[LOG_PATH]}" % args.glue["gateway_url"])
        args.glue["zuul_default_log_site"] = get_default(
            zuul_config, "default_log_site", "sflogs")
        args.glue["zuul_extra_gerrits"] = zuul_config.get("gerrit_connections",
                                                          [])

        # Zuul known hosts
        args.glue["zuul_ssh_known_hosts"] = []
        if "gerrit" in args.glue["roles"]:
            args.glue["zuul_ssh_known_hosts"].append({
                "host_packed": "[%s]:29418" % args.glue["gerrit_host"],
                "host": args.glue["gerrit_host"],
                "port": "29418",
            })
        for logserver in zuul_config.get("external_logserver", []):
            args.glue["zuul_ssh_known_hosts"].append({
                "host_packed": logserver.get("hostname", logserver["name"]),
                "host": logserver.get("hostname", logserver["name"]),
                "port": "22",
            })
        for extra_gerrit in args.glue.get("zuul_extra_gerrits", []):
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

        for static_node in args.glue.get("zuul_static_nodes", []):
            args.glue["zuul_ssh_known_hosts"].append({
                "host_packed": static_node.get("hostname"),
                "host": static_node.get("hostname"),
                "port": 22
            })


class ZuulMerger(Component):
    role = "zuul-merger"

    def usage(self, parser):
        parser.add_argument("--zuul-merger", action="append",
                            metavar="IP[:hostname]",
                            help="Define external zuul-merger")

    def argparse(self, args):
        if not args.zuul_merger:
            return
        for zm in args.zuul_merger:
            if ":" in zm:
                ip, hostname = zm.split(':')
                public_url = "http://%s" % hostname
            else:
                ip, hostname = zm, None
                public_url = None

            # Look for already defined host and count zuul-merger
            zm_count = 0
            found = False
            for host in args.sfarch["inventory"]:
                if host["ip"] == ip:
                    found = True
                    break
                if "zuul-merger" in host["roles"]:
                    zm_count += 1
            if found:
                continue

            args.save_arch = True
            if not hostname:
                hostname = "zm%02d.%s" % (zm_count, args.sfconfig["fqdn"])
            host = {"name": hostname, "hostname": hostname, "ip": ip,
                    "roles": ["zuul-merger"]}
            if public_url:
                host["public_url"] = public_url
            args.sfarch["inventory"].append(host)


class ZuulLauncher(Component):
    role = "zuul-launcher"

    def prepare(self, args):
        zuul_config = args.sfconfig.get('zuul', {})
        if zuul_config.get('default_log_site', 'sflogs') == 'sflogs':
            # Need logserver role
            self.require_roles = ['logserver']
        super(ZuulLauncher, self).prepare(args)

    def configure(self, args, host):
        args.glue["jobs_zmq_publishers"].append(
            "tcp://%s:8888" % args.glue["zuul_launcher_host"])
        args.glue["loguser_authorized_keys"].append(
            args.glue["jenkins_rsa_pub"])
        args.glue["zuul_static_nodes"] = args.sfconfig.get(
            'zuul', {}).get('static_nodes', [])
