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


class LogServer(Component):
    def prepare(self, args):
        super(LogServer, self).prepare(args)
        args.glue["loguser_authorized_keys"] = []

    def configure(self, args, host):
        args.glue["logservers"].append({
            "name": "sflogs",
            "host": args.glue["logserver_host"],
            "user": "loguser",
            "path": "/var/www/logs",
        })
        if args.glue["logserver_host"] != args.glue["install_server_host"]:
            args.glue.setdefault("zuul3_ssh_known_hosts", []).append({
                "host_packed": args.glue["logserver_host"],
                "host": args.glue["logserver_host"],
                "port": 22
            })
        args.glue["logs_expiry"] = args.sfconfig["logs"]["expiry"]
