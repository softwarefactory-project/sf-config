#!/bin/sh

set -x
set -e

# Git config complains about HOME env var missing ...
export HOME=/root

CLONETEMPDIR="/tmp/All-projects"

[ -d "$CLONETEMPDIR" ] && rm -Rf $CLONETEMPDIR
git init $CLONETEMPDIR
pushd $CLONETEMPDIR
git remote add origin ssh://gerrit/All-Projects
git fetch origin refs/meta/config:refs/remotes/origin/meta/config
git checkout meta/config

# As this we be called by ansible if gerrit.war change then
# be sure to not overwrite project.config if modified
# by someone else.
[ -z "$1" -a $(git log --pretty=oneline | wc -l) -eq 1 ] && {
    cp /usr/share/sf-config/defaults/project.config .
}

git status
git diff
git add *

# git returns exit code 1 in case there is nothing to do
# This fails during an upgrade, thus always return exit code 0
cmsg="Provide the default config"
git commit -a -m"$cmsg" || true
git push origin meta/config:meta/config
popd
rm -Rf $CLONETEMPDIR
