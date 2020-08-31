#!/bin/env python3
# Copyright 2020, Red Hat
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

""" Some functions to manipulate notedb """

import os
import subprocess
import functools
from pathlib import Path
import yaml
from hashlib import sha1

cache = Path("~/.cache").expanduser()


@functools.lru_cache(maxsize=1)
def fqdn():
    return yaml.safe_load(open("/etc/software-factory/sfconfig.yaml"))["fqdn"]


def giturl(reponame):
    return "/var/lib/gerrit/git/" + reponame + ".git"


def execute(argv, cwd=None):
    if subprocess.Popen(argv, cwd=cwd).wait():
        raise RuntimeError("%s: failed" % ' '.join(argv))


def git(gitdir):
    def func(*argv):
        execute(["git"] + list(argv), cwd=str(gitdir))
    return func


def clone(url, dest):
    if not dest.exists():
        execute(["git", "clone", url, str(dest)])
    gitrepo = git(dest)
    for (k,v) in [("user.name", "SF initial configurator"),
                  ("user.email", "admin@" + fqdn())]:
        gitrepo("config", k, v)
    return gitrepo


def commit_and_push(repo, message, ref):
    try:
        repo("commit", "-a", "-m", message)
    except RuntimeError:
        return
    repo("push", "origin", "HEAD:" + ref)


def allow_push():
    """Ensure admin can push notedb refs"""
    repo = clone(giturl("All-Projects"), cache / "All-Projects")
    repo("config", "-f", "project.config", "access.refs/*.push",
         "group Administrators", ".*group Administrators")
    commit_and_push(repo, "Enable admin to push refs", "refs/meta/config")


def sha1sum(strdata):
    m = sha1()
    m.update(strdata.encode('utf8'))
    return m.hexdigest()


def fix_cauth_external_id(filename):
    filecontent = filename.read_text()
    for fileline in filecontent.split('\n'):
        if fileline.startswith("[externalId \"username:"):
            extid = fileline.split("\"")[1]
            _scheme, name = extid.split(":", 1)
            newfilename = filename.parent / sha1sum("gerrit:" + name)
            newfilename.write_text(filecontent.replace(
                "[externalId \"username:",
                "[externalId \"gerrit:"))
            print("Created gerrit scheme:", newfilename)


def fix_cauth_external_ids():
    """Update externalId to use `gerrit` scheme instead of `username`"""
    all_users = cache / "All-Users"
    repo = clone(giturl("All-Users"), all_users)
    repo("fetch", "origin", "refs/meta/external-ids")
    try:
        repo("checkout", "-b", "extId", "FETCH_HEAD")
    except RuntimeError:
        pass
    list(map(fix_cauth_external_id,
             filter(lambda fp: fp.is_file(),
                    map(lambda fn: all_users / fn,
                        os.listdir(all_users)))))
    repo("add", ".")
    commit_and_push(
        repo, "Update external id to gerrit scheme", "refs/meta/external-ids")


if __name__ == "__main__":
    allow_push()
    fix_cauth_external_ids()
