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

import argparse
import os
import subprocess
from pathlib import Path
from hashlib import sha1


cache = Path("~/.cache/git").expanduser()
cache.mkdir(exist_ok=True, parents=True)


def giturl(reponame):
    return "/var/lib/gerrit/git/" + reponame + ".git"


def execute(argv, cwd=None):
    if subprocess.Popen(argv, cwd=cwd).wait():
        raise RuntimeError("%s: failed" % ' '.join(argv))
    return True


def ignore_error(cmd):
    try:
        return cmd()
    except RuntimeError:
        pass


def git(gitdir):
    def func(*argv):
        if argv[0] == "file":
            # Fake "file" command that return a file Path inside the checkout
            return gitdir / argv[1]
        return execute(["git"] + list(argv), cwd=str(gitdir))
    return func


def clone(url, dest, fqdn):
    if not dest.exists():
        execute(["git", "clone", url, str(dest)])
    gitrepo = git(dest)
    for (k, v) in [("user.name", "SF initial configurator"),
                   ("user.email", "admin@" + fqdn)]:
        gitrepo("config", k, v)
    return gitrepo


def checkout(repo, branch, ref):
    repo("fetch", "origin", ref)
    repo("checkout", "-B", branch, "FETCH_HEAD")


def new_orphan(repo, branch):
    ignore_error(lambda: repo("branch", "-D", branch))
    repo("checkout", "--orphan", branch)
    repo("rm", "--cached", "-r", "--", ".")
    repo("clean", "-d", "-f", "-x")


def commit_and_push(repo, message, ref):
    ignore_error(lambda: repo("commit", "-a", "-m", message))
    # TODO: check if ref is already pushed
    ignore_error(lambda: repo("push", "origin", "HEAD:" + ref))


def allow_push(fqdn):
    """Ensure admin can push notedb refs"""
    repo = clone(giturl("All-Projects"), cache / "All-Projects", fqdn)
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
            break


# TODO: check why is this necessary
def fix_cauth_external_ids(fqdn):
    """Update externalId to use `gerrit` scheme instead of `username`"""
    all_users = cache / "All-Users"
    repo = clone(giturl("All-Users"), all_users, fqdn)
    checkout(repo, "extId", "refs/meta/external-ids")
    list(map(fix_cauth_external_id,
             filter(lambda fp: fp.is_file(),
                    map(lambda fn: all_users / fn,
                        os.listdir(all_users)))))
    repo("add", ".")
    commit_and_push(
        repo, "Update external id to gerrit scheme", "refs/meta/external-ids")


def mk_ref_id(refname):
    """ Create gerrit CD/ABCD name
    >>> mk_ref_id("1")
    "01/1"
    >>> mk_ref_id("41242")
    "42/41242"
    """
    refid = refname[-2:] if len(refname) > 1 else ("0" + refname[-1])
    return refid + "/" + refname


def mk_ref(name):
    def func(refname):
        return "refs/" + name + "/" + mk_ref_id(refname)
    return func


mk_user_ref = mk_ref("users")
mk_group_ref = mk_ref("groups")


def get_group_id(all_users, group_name):
    checkout(all_users, "meta_config", "refs/meta/config")
    groups = all_users("file", "groups").read_text()
    group = list(
        filter(lambda s: s and s[-1] == group_name,
               map(str.split, groups.split("\n"))))
    if len(group) == 1:
        return group[0][0]


def create_admin_user(fqdn, pubkey):
    all_users = cache / "All-Users"
    repo = clone(giturl("All-Users"), all_users, fqdn)
    admin_ref = mk_user_ref("1")
    admin_mail = "admin@" + fqdn

    # Create user
    try:
        checkout(repo, "user_admin", admin_ref)
    except RuntimeError:
        new_orphan(repo, "user_admin")
    (all_users / "account.config").write_text("\n".join([
        "[account]",
        "\tfullName = Administrator",
        "\tpreferredEmail = " + admin_mail,
        ""
    ]))
    (all_users / "authorized_keys").write_text(pubkey + "\n")
    repo("add", "account.config", "authorized_keys")
    commit_and_push(repo, "Initialize admin user", admin_ref)

    # Add user to admin group
    admin_group_ref = mk_group_ref(get_group_id(repo, "Administrators"))
    try:
        checkout(repo, "group_admin", admin_group_ref)
    except RuntimeError:
        # For some reason, group ref can be AB/ABCD
        r, g, _, i = admin_group_ref.split('/')
        admin_group_ref = '/'.join([r, g, i[:2], i])
        checkout(repo, "group_admin", admin_group_ref)
    members_file = repo("file", "members")
    if members_file.exists():
        members = members_file.read_text().split('\n')
    else:
        members = []
    if "1" not in members:
        members_file.write_text("\n".join(members + ["1", ""]))
    repo("add", "members")
    commit_and_push(
        repo, "Add admin user to Administrators group", admin_group_ref)

    # Create external id
    try:
        checkout(repo, "external_ids", "refs/meta/external-ids")
    except RuntimeError:
        new_orphan(repo, "external_ids")
    repo("file", sha1sum("username:admin")).write_text("\n".join([
        "[externalId \"username:admin\"]",
        "\taccountId = 1",
        ""
    ]))
    repo("file", sha1sum("mailto:" + admin_mail)).write_text("\n".join([
        "[externalId \"mailto:" + admin_mail + "\"]",
        "\taccountId = 1",
        "\temail = " + admin_mail,
        ""
    ]))
    repo("add", ".")
    commit_and_push(repo, "Add admin external id", "refs/meta/external-ids")


def usage():
    parser = argparse.ArgumentParser(description="notedb-tools")
    parser.add_argument("--fqdn")
    parser.add_argument("--pubkey")
    parser.add_argument("action", choices=["init", "migrate"])
    return parser.parse_args()


if __name__ == "__main__":
    args = usage()
    if not args.fqdn:
        args.fqdn = "sftests.com"
    if args.action == "migrate":
        allow_push(args.fqdn)
        fix_cauth_external_ids(args.fqdn)
    elif args.action == "init":
        if not args.pubkey:
            raise RuntimeError("Need a public ssh key --pubkey argument")
        create_admin_user(args.fqdn, args.pubkey)
        cookiedir = Path("/var/lib/gerrit/.init")
        cookiedir.mkdir(exist_ok=True)
        (cookiedir / "admin_email").write_text("admin@" + args.fqdn)
