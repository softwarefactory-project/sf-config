#!/bin/env python3
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
#
# Submit change and wait for CI vote
# --approve also vote +2 and wait for change to be merged
# --failure make the script succeed when CI vote -1

import os
import argparse
import subprocess
import time
import json
import sys


def execute(cmd):
    if globals()['debug']:
        print("Debug: execute: %s" % cmd)
    p = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    if p.wait():
        fail(p.stdout.read().decode('utf-8'))
    return p.stdout.read().decode("utf-8")


def fail(msg):
    sys.stderr.write("%s\n" % msg)
    exit(1)


def get_ci_verify_vote(json_object):
    if (u'currentPatchSet' not in json_object or
            u'approvals' not in json_object[u'currentPatchSet']):
        return None
    for a in json_object[u'currentPatchSet'][u'approvals']:
        if a[u'by'][u'name'] in ('Zuul CI',) and \
           a[u"type"] == "Verified":
            return int(a[u'value'])


def wait_for_merge(query, retry):
    while retry > 0:
        if "MERGED" in execute(query):
            return
        retry -= 1
        time.sleep(1)
    fail("Change wasn't merged: %s" % execute(query))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.getcwd())
    parser.add_argument("--delay", type=int, default=120)
    parser.add_argument("--abandon", action="store_const", const=True)
    parser.add_argument("--approve", action="store_const", const=True)
    parser.add_argument("--failure", action="store_const", const=True)
    parser.add_argument("--recheck", action="store_const", const=True)
    parser.add_argument("--rebase", action="store_const", const=True)
    parser.add_argument("--debug", action="store_const", const=True)
    parser.add_argument("--review-id", type=int, default=0)
    args = parser.parse_args()

    globals()['debug'] = args.debug

    os.chdir(args.repository)

    # Check gerrit host
    if not os.path.isfile(".gitreview"):
        fail("%s: Project is missing .gitreview" % args.repository)
    ghost = list(filter(lambda x: x.startswith("host="),
                        open(".gitreview").readlines()))
    ghost = ghost[0].split('=')[1].strip()

    # Set gitreview.username configuration
    if "username" not in open("%s/.gitconfig" % os.environ["HOME"]).read():
        execute("git config --global gitreview.username admin")

    gr_opts = ''
    if args.debug:
        gr_opts = '-v'

    if args.review_id:
        print(execute("/usr/local/bin/git-review %s -d %s"
                      % (gr_opts, args.review_id)))
        sha = execute("git log -n1 --pretty=format:%H")
    else:
        # Submit change
        if "Change-Id:" in execute("git log -n 1"):
            print(execute("/usr/local/bin/git-review %s -y" % gr_opts))
        else:
            print(execute("/usr/local/bin/git-review %s -yi" % gr_opts))
        # get current branch
        current_ref = open(".git/HEAD").read()
        if current_ref.startswith('ref: '):
            current_ref = current_ref[len('ref: '):]
        if current_ref.endswith('\n'):
            current_ref = current_ref[:-1]
        sha = open(".git/%s" % current_ref).read()

    # Give CI agent some time to start test
    time.sleep(2)

    cmd = "ssh -p 29418 %s gerrit" % ghost
    if args.recheck:
        return execute("%s review --message recheck %s" % (cmd, sha))

    if args.rebase:
        return execute("%s review --rebase %s" % (cmd, sha))

    if args.abandon:
        return execute("%s review --abandon %s" % (cmd, sha))

    if args.approve:
        execute("%s review --code-review +2 --workflow +1 %s" % (cmd, sha))

    query = "query --format JSON --current-patch-set %s" % sha
    retry = args.delay
    while retry > 0:
        q = execute("%s %s" % (cmd, query))
        # Get CI agent's Verify vote
        ci_note = get_ci_verify_vote(json.loads(q.split('\n')[0]))
        if ci_note is not None and ci_note > 0:
            if args.failure:
                fail("CI agent voted %d in --failure mode")
            if (args.approve and ci_note == 2) or not args.approve:
                if args.approve:
                    # Wait until status:MERGED when approved
                    wait_for_merge("%s %s" % (cmd, query), retry)
                # CI agent voted +1/+2
                exit(0)
        elif ci_note is not None and ci_note < 0:
            if args.failure:
                # Ignore CI failure
                exit(0)
            fail("CI agent voted %d" % ci_note)
        retry -= 1
        time.sleep(1)
    if args.approve and ci_note == 1:
        fail("CI agent didn't +2 approved change")
    if ci_note is None:
        fail("CI agent didn't vote")
    fail("CI agent voted 0")


main()
