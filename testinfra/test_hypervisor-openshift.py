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

import utils
import yaml


class TestHypervisorOpenShift(utils.Base):
    def test_oc_login(self, host):
        assert host.check_output("oc login -u developer -p devel "
                                 "https://localhost:8443 "
                                 "--insecure-skip-tls-verify=true")

    def test_workers_are_isolated(self, host):
        group_vars = yaml.safe_load(open(
            "/var/lib/software-factory/ansible/group_vars/all.yaml"))
        if group_vars.get("enable_insecure_workers") is not True:
            # Make sure managesf internal url access fails
            assert host.run("curl --connect-timeout 3 %s" % group_vars[
                "managesf_internal_url"]).rc in (7, 28)
