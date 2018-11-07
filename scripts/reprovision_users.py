#!/usr/bin/python
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

from sys import argv, exit
import yaml
import requests
import json
import os

from pysflib import sfauth


if __name__ == '__main__':
    cwd = os.getcwd()
    conf_path = argv[2]
    with open(conf_path) as f:
        config = yaml.load(f)
    admin_pass = config['authentication']['admin_password']
    url = config['fqdn']
    cookie = {'auth_pubtkt': sfauth.get_cookie(url, 'admin',
                                               admin_pass)}

    if argv[1] == 'dump':
        try:
            os.remove('/tmp/users_provision.json')
        except OSError:
            pass
        o = requests.get('http://%s/manage/project/membership/' % url,
                         cookies=cookie)
        with open('/tmp/users_provision.json', 'w') as f:
            json.dump(o.json(), f)
    elif argv[1] == 'provision':
        with open('/tmp/users_provision.json') as f:
            users = json.load(f)
        for user in users:
            username, email, full_name = user
            _user = {"full_name": full_name,
                     "email": email,
                     "username": username,
                     "ssh_keys": [],
                     "external_id": -1}
            data = json.dumps(_user,
                              default=lambda o: o.__dict__)
            headers = headers = {"Content-type": "application/json"}
            requests.post('http://%s/manage/services_users/' % url,
                          data=data, headers=headers,
                          cookies=cookie)
        os.remove('/tmp/users_provision.json')
    else:
        exit('supported arguments: dump|provision')
