#!/bin/env python

import yaml
import argparse

DEFAULT_ACL="""
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
    p.add_argument("--repo")
    p.add_argument("--core")
    p.add_argument("output")
    return p.parse_args()


def main():
    args = usage()

    resources = {
        'repos': {
            args.repo: {
                'description': 'The %s repository' % args.repo,
                'acl': '%s-acl' % args.repo
            }
        },
        'acls': {
            '%s-acl' % args.repo: {
                'file': DEFAULT_ACL.format(repo=args.repo),
                'groups': ['%s-core' % args.repo]
            }
        },
        'groups': {
            '%s-core' % args.repo: {
                'description': 'The %s core group' % args.repo,
                'members': [args.core]
            }
        }
    }
    with open(args.output, "w") as of:
        yaml.safe_dump({'resources': resources}, of, default_flow_style=False)

if __name__ == "__main__":
    main()
