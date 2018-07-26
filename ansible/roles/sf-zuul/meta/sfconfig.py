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


class ZuulScheduler(Component):
    role = "zuul-scheduler"
    require_role = ["nodepool", "zookeeper"]

    def configure(self, args, host):
        args.glue["zuul_host"] = args.glue["zuul_scheduler_host"]
        self.add_mysql_database(args, "zuul", hosts=list(set((
            args.glue["zuul_scheduler_host"], args.glue["zuul_web_host"]
        ))))
        self.get_or_generate_ssh_key(args, "zuul_rsa")
        self.get_or_generate_ssh_key(args, "zuul_worker_rsa")
        self.get_or_generate_cert(args, "gearman", host["hostname"])
        args.glue["zuul_pub_url"] = "%s/zuul/" % args.glue["gateway_url"]
        args.glue["zuul_mysql_host"] = args.glue["mysql_host"]

        args.glue["zuul_periodic_pipeline_mail_rcpt"] = args.sfconfig[
            "zuul"]["periodic_pipeline_mail_rcpt"]

        # Extra settings
        zuul_config = args.sfconfig.get("zuul", {})
        args.glue["zuul_default_retry_attempts"] = zuul_config[
            "default_retry_attempts"]
        args.glue["zuul_upstream_zuul_jobs"] = zuul_config[
            "upstream_zuul_jobs"]
        args.glue["zuul_success_log_url"] = get_default(
            zuul_config, "success_log_url",
            "%s/logs/{build.uuid}/" % args.glue["gateway_url"]
        )
        args.glue["zuul_failure_log_url"] = get_default(
            zuul_config, "failure_log_url",
            "%s/logs/{build.uuid}/" % args.glue["gateway_url"]
        )

        if "logserver" in args.glue["roles"]:
            args.glue["zuul_ssh_known_hosts"].append({
                "host_packed": args.glue["logserver_host"],
                "host": args.glue["logserver_host"],
                "port": 22
            })


class ZuulExecutor(Component):
    role = "zuul-executor"
    require_role = ["zuul-scheduler"]

    def configure(self, args, host):
        args.glue["executor_hosts"].append(host["hostname"])


class ZuulWeb(Component):
    role = "zuul-web"
    require_role = ["zuul-scheduler"]

    def configure(self, args, host):
        args.glue["zuul_web_url"] = "http://%s:%s" % (
            args.glue["zuul_web_host"], args.defaults["zuul_web_port"])
        args.glue["zuul_ws_url"] = "ws://%s:%s" % (
            args.glue["zuul_web_host"], args.defaults["zuul_web_port"])
