# Copyright (C) 2017 Red Hat
#
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

from sfconfig.utils import get_or_generate_ssh_key


def configure(args, host, sfconf, arch, glue, secrets, defaults):
    glue["jenkins_internal_url"] = "http://%s:%s/jenkins/" % (
        host["hostname"], defaults["jenkins_http_port"])
    glue["jenkins_api_url"] = "http://%s:%s/jenkins/" % (
        host["hostname"], defaults["jenkins_api_port"])
    glue["jenkins_pub_url"] = "%s/jenkins/" % glue["gateway_url"]
    glue["jobs_zmq_publishers"].append(
        "tcp://%s:8889" % glue["jenkins_host"])
    glue.update(get_or_generate_ssh_key(args, "jenkins_rsa"))
