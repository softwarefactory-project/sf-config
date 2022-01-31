#!/bin/env python3

# Copyright 2021, Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import argparse
import json

import kazoo.client
import kazoo.exceptions

parser = argparse.ArgumentParser(
    description="Clean ZK nodepool database tool."
    "For example: /zuul/events/connection/softwarefactory-project.io/events "
    "To get queue, you can use command: zkCli.sh ls /zuul/events/connection/"
)
parser.add_argument('--queue', help="provide path to the queue",
                    required=True)
parser.add_argument('--host', help="Specify zookeeper host",
                    default='zookeeper')
parser.add_argument('--all', help="Remove all events no matter what is "
                    "the type",
                    action="store_true")
parser.add_argument('--type', help="Remove specific event type"
                    "e.g. ref-replication-scheduled or dropped-output ")
parser.add_argument('--refstatus', help="Remove specific ref status"
                    "eg. NON_EXISTING")
args = parser.parse_args()

client = kazoo.client.KazooClient(hosts=args.host)
client.start()

events = client.get_children(args.queue)
patches = list(map(lambda n: args.queue.rstrip("/") + "/" + n, events))
print("Current lenght of the queue %s is %s" % (args.queue, len(patches)))

if args.all:
    for p in patches:
        try:
            client.delete(p, recursive=True)
        except kazoo.exceptions.NoNodeError:
            print("Can not remove %s" % p)
elif args.type or args.refstatus:
    for p in patches:
        try:
            data, _ = client.get(p)
            jdata = json.loads(data).get('payload')
            if (jdata.get('type', '') == args.type) or (
                    jdata.get('refStatus', '') == args.refstatus):
                print("Cleaning %s that contain %s" % (p, jdata))
                client.delete(p, recursive=True)
        except kazoo.exceptions.NoNodeError:
            print("Can not remove %s" % p)
