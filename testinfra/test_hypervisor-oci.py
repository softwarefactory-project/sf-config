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


class TestHypervisorOCI(utils.Base):
    def test_slaves_are_running(self, host):
        assert host.check_output("runc list -q")

    def test_slaves_are_isolated(self, host):
        group_vars = yaml.safe_load(open(
            "/var/lib/software-factory/ansible/group_vars/all.yaml"))
        if group_vars.get("enable_insecure_slave") != True:
            # Make sure managesf internal url access fails
            assert host.run("curl %s" % group_vars[
                "managesf_internal_url"]).rc == 7
