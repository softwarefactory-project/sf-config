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


class TestGerrit:
    def test_service_running_and_enabled(self, host):
        gerrit = host.service("gerrit")
        assert gerrit.is_running
        assert gerrit.is_enabled

    def test_ci_connected(self, host):
        skt = host.socket("tcp://29418")
        assert skt.is_listening, "Gerrit sshd server is not listening"
        assert skt.clients, "No CI connected to gerrit socket"
