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


class TestTelegraf(utils.Base):
    def test_telegraf_service_running_and_enabled(self, host):
        service = host.service('telegraf')
        assert service.is_running
        assert service.is_enabled

    def test_telgraft_statsd_intput_plugin(self, host):
        if 'nodepool3' or 'zuul3' in self.enabled_roles():
            statsd_config = '/etc/telegraf/telegraf.d/statsd.conf'
            assert host.file(statsd_config).exists
            assert host.socket("udp://8125").is_listening
