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


class Gerrit(Component):
    def usage(self, parser):
        parser.add_argument("--provision-demo", action='store_true',
                            help="Provision demo projects")

    def argparse(self, args):
        args.glue["provision_demo"] = args.provision_demo

    def configure(self, args, host):
        self.get_or_generate_ssh_key(args, "gerrit_service_rsa")
        self.get_or_generate_ssh_key(args, "gerrit_admin_rsa")
        self.add_mysql_database(args, "gerrit",
                                hosts=[args.glue["managesf_host"]])
        args.glue["gerrit_pub_url"] = "%s/r/" % args.glue["gateway_url"]
        args.glue["gerrit_internal_url"] = "http://%s:%s/r/" % (
            args.glue["gerrit_host"], args.defaults["gerrit_port"])
        args.glue["gerrit_email"] = "admin@%s" % args.sfconfig["fqdn"]
        if args.sfconfig["network"]["disable_external_resources"]:
            args.glue["gerrit_replication"] = False
        args.glue["config_connection_name"] = "gerrit"
        args.glue["config_location"] = "git+ssh://gerrit/config"
        args.glue["sf_jobs_location"] = "git+ssh://gerrit/sf-jobs"
        args.glue["zuul_jobs_location"] = "git+ssh://gerrit/zuul-jobs"
        args.glue["public_config_location"] = "%s/r/config" % (
            args.glue["gateway_url"])
