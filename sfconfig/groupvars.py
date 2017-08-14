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

import uuid

from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


def load(args):
    """Load roles defaults and generate CHANGE_ME secrets"""
    # Generate all variable when the value is CHANGE_ME and collect defaults
    args.defaults = {}
    for role in args.glue["roles"]:
        role_vars = yaml_load("%s/ansible/roles/sf-%s/defaults/main.yml" % (
                              args.share, role))
        args.defaults.update(role_vars)
        for key, value in role_vars.items():
            if str(value).strip().replace('"', '') == 'CHANGE_ME':
                if key not in args.secrets:
                    args.secrets[key] = str(uuid.uuid4())

    # Set default glue
    args.glue["gateway_url"] = "https://%s" % args.sfconfig["fqdn"]

    if args.sfconfig["debug"]:
        for service in ("managesf", "zuul", "nodepool"):
            args.glue["%s_loglevel" % service] = "DEBUG"
            args.glue["%s_root_loglevel" % service] = "INFO"

    # Save secrets to new secrets file
    yaml_dump(args.secrets, open("%s/secrets.yaml" % args.lib, "w"))
    args.glue.update(args.secrets)
