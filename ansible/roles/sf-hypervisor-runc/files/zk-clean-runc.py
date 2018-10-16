#!/opt/rh/rh-python35/root/usr/bin/python
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

import kazoo.client
import os.path
import json

client = kazoo.client.KazooClient(hosts="zookeeper")
client.start()


def get_type(t):
    try:
        if isinstance(t, list):
            return t[0]
        else:
            return t
    except Exception:
        return ""


print("Removing any oci requests")
try:
    requests = client.get_children("/nodepool/requests")
except Exception:
    requests = []
for req in requests:
    req_path = os.path.join("/nodepool/requests", req)
    req = json.loads(client.get(req_path)[0].decode('utf-8'))
    if get_type(req["node_types"]).endswith("-oci"):
        print("Deleting %s" % req_path)
        client.delete(req_path, recursive=True)

print("Removing any oci nodes")
try:
    nodes = client.get_children("/nodepool/nodes")
except Exception:
    nodes = []
for node in nodes:
    node_path = os.path.join("/nodepool/nodes", node)
    node = json.loads(client.get(node_path)[0].decode('utf-8'))
    if get_type(node["type"]).endswith("-oci"):
        print("Deleting %s" % node_path)
        client.delete(node_path, recursive=True)
