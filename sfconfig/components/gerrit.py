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
    role = "gerrit"
    require_roles = ["mysql"]

    def configure(self):
        self.get_or_generate_ssh_key("gerrit_service_rsa")
        self.get_or_generate_ssh_key("gerrit_admin_rsa")
        self.add_mysql_database("gerrit", hosts=[self.glue["managesf_host"]])
        self.glue["gerrit_pub_url"] = "%s/r/" % self.glue["gateway_url"]
        self.glue["gerrit_internal_url"] = "http://%s:%s/r/" % (
            self.glue["gerrit_host"], self.defaults["gerrit_port"])
        self.glue["gerrit_email"] = "gerrit@%s" % self.sfmain["fqdn"]
        if self.sfmain["network"]["disable_external_resources"]:
            self.glue["gerrit_replication"] = False
