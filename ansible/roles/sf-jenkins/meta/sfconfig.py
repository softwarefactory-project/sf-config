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


class Jenkins(Component):
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
