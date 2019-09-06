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
from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


class Base(Component):
    def configure(self, args, host):
        update_secrets = False
        previous_vars = yaml_load("%s/group_vars/all.yaml" % args.ansible_root)
        if not args.secrets.get('sf_service_user_password_hash') or \
           previous_vars.get('sf_service_user_password') != \
           args.secrets['sf_service_user_password']:
            update_secrets = True
            args.secrets["sf_service_user_password_hash"] = self.hash_password(
                args.secrets["sf_service_user_password"])
        if update_secrets and not args.skip_setup:
            yaml_dump(args.secrets, open("%s/secrets.yaml" % args.lib, "w"))
            args.glue.update(args.secrets)
