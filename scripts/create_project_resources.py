#!/bin/env python
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

import yaml
import argparse

DEFAULT_ACL = """
[access "refs/*"]
  owner = group {repo}-core
[access "refs/heads/*"]
  label-Code-Review = -2..+2 group {repo}-core
  label-Verified = -2..+2 group {repo}-core
  label-Workflow = -1..+1 group {repo}-core
  label-Workflow = -1..+0 group Registered Users
  submit = group {repo}-core
  read = group Registered Users
[access "refs/meta/config"]
  read = group {repo}-core
  read = group Registered Users
[receive]
  requireChangeId = true
[submit]
  mergeContent = false
  action = fast forward only
"""


def usage():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", action='append')
    p.add_argument("--core")
    p.add_argument("output")
    return p.parse_args()


def main():
    args = usage()
    name = args.repo[0]

    resources = {
        'repos': {
            name: {
                'description': 'The %s repository' % name,
                'acl': '%s-acl' % name
            }
        },
        'acls': {
            '%s-acl' % name: {
                'file': DEFAULT_ACL.format(repo=name),
                'groups': ['%s-core' % name]
            }
        },
        'groups': {
            '%s-core' % name: {
                'description': 'The %s core group' % name,
                'members': [args.core]
            }
        }
    }
    if len(args.repo) > 1:
        for repo in args.repo[1:]:
            resources['repos'][repo] = {
                'description': 'The %s repository' % repo,
                'acl': '%s-acl' % name
            }
    with open(args.output, "w") as of:
        yaml.safe_dump({'resources': resources}, of, default_flow_style=False)

if __name__ == "__main__":
    main()
