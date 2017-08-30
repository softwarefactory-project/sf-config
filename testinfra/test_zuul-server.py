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


class TestZuulServer:
    def test_server_running_and_enabled(self, host):
        server = host.service("zuul-server")
        assert server.is_running
        assert server.is_enabled

    def test_server_configured(self, host):
        l = host.file("/etc/zuul/layout.yaml")
        assert l.contains("name: check"), "Layout doesn't have check pipeline"
        assert l.contains("name: config"), "Layout doesn't have config project"
        gearman = host.socket("tcp://0.0.0.0:4730")
        assert gearman.is_listening, "Gearman server is not listening"
        assert gearman.clients, "No gearman clients are connected"
