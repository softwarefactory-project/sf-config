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


class TestZookeeper(utils.Base):
    def test_service_running_and_enabled(self, host):
        srv = host.service("zookeeper")
        assert srv.is_running
        assert srv.is_enabled
        assert host.socket("tcp://2181").is_listening

    def test_client_are_connected(self, host):
        expected_clients = 0
        for role in self.enabled_roles():
            if role in ("nodepool-builder", "nodepool-launcher",
                        "nodepool3-builder", "nodepool3-launcher"):
                expected_clients += 1
        skt = host.socket("tcp://2181")
        assert len(skt.clients) >= expected_clients
