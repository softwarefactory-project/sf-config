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

""" This is just a snipset that needs to be converted as an ansible library

E.g. call like this:
./demo.py \
    /etc/software-factory/my-zuul-test-key.pem \
    13350 \
    repos/TristanAlt/demo-project/pulls/2/requested_reviewers \
    POST \
    '{"reviewers": ["TristanAlt"]}'

=> Adds a reviewer to https://github.com/TristanAlt/demo-project/pull/2
"""

import sys
import datetime
import jwt
import json

import github3
import requests


try:
    key_data = open(sys.argv[1]).read()
    app_id = int(sys.argv[2])

    api_url = sys.argv[3]
    api_action = sys.argv[4]
    api_data = json.loads(sys.argv[5])
except Exception:
    print("usage: %s <key-path> <app-id>" % sys.argv[0])
    raise


#############
# Constants #
#############
class UTC(datetime.tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)


utc = UTC()
PREVIEW_JSON_ACCEPT = 'application/vnd.github.machine-man-preview+json'
base_url = "https://api.github.com"

###################
# Prepare headers #
###################
now = datetime.datetime.now(utc)
expiry = now + datetime.timedelta(minutes=5)

data = {'iat': now, 'exp': expiry, 'iss': app_id}
app_token = jwt.encode(data,
                       key_data,
                       algorithm='RS256').decode('utf-8')

headers = {'Accept': PREVIEW_JSON_ACCEPT,
           'Authorization': 'Bearer %s' % app_token}

github = github3.GitHub()


#######################
# Get installation ID #
#######################
url = '%s/app/installations' % base_url

response = requests.get(url, headers=headers)
response.raise_for_status()
installation_id = response.json()[0]['id']
print("installation_id = ", installation_id)

####################
# Get Access Token #
####################
url = "%s/installations/%s/access_tokens" % (base_url, installation_id)

response = requests.post(url, headers=headers)
response.raise_for_status()

data = response.json()
token = data['token']
headers = {'Accept': PREVIEW_JSON_ACCEPT, 'Authorization': 'token %s' % token}

###############
# Do API call #
###############
url = "%s/%s" % (base_url, api_url)

response = requests.request(api_action, url, headers=headers, json=api_data)
response.raise_for_status()
print(response.text)
