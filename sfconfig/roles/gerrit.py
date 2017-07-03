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
    glue["gerrit_pub_url"] = "%s/r/" % glue["gateway_url"]
    glue["gerrit_internal_url"] = "http://%s:%s/r/" % (
        host["hostname"], defaults["gerrit_port"])
    glue["gerrit_email"] = "gerrit@%s" % sfconf["fqdn"]
    glue["gerrit_mysql_host"] = glue["mysql_host"]
    glue["mysql_databases"]["gerrit"] = {
        'hosts': list(set(('localhost',
                           host["hostname"],
                           glue["managesf_host"],
                           ))),
        'user': 'gerrit',
        'password': secrets['gerrit_mysql_password'],
    }
    glue.update(get_or_generate_ssh_key(args, "gerrit_service_rsa"))
    glue.update(get_or_generate_ssh_key(args, "gerrit_admin_rsa"))
