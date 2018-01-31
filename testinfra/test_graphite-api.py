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


class TestGraphiteApi:
    def test_carbon_configuration_file(self, host):
        carbon_config_files = ['storage-aggregation.conf',
                               'storage-schemas.conf']
        for carbon_file in carbon_config_files:
            assert host.file('/etc/carbon/%s' % carbon_file).exists

    def test_carbon_service_running_and_enabled(self, host):
        service = host.service("carbon-cache")
        assert service.is_running
        assert service.is_enabled
        assert host.socket("tcp://0.0.0.0:2003").is_listening

    def test_httpd_graphite_configuration_files(self, host):
        graphite_config_files = ['graphite_api_htpasswd',
                                 'conf.d/graphite-api.conf']
        for graphite_file in graphite_config_files:
            assert host.file('/etc/httpd/%s' % graphite_file).exists

    def test_httpd_graphite_vhost(self, host):
        assert host.socket("tcp://8008").is_listening
