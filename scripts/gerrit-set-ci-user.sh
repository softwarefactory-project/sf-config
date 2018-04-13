#!/bin/sh

set -x
set -e

USER_NAME="${1}"
USER_SSHKEY="${2}"
USER_MAIL="${3}"
# Capitalize user_name, e.g. "Zuul CI"
USER_FULLNAME="$(tr '[:lower:]' '[:upper:]' <<< ${USER_NAME:0:1})${USER_NAME:1} CI"

# Check if user does not exist yet
USER_EXISTS=$(ssh gerrit gerrit ls-members \"Non-Interactive Users\" | awk '{ print $2 }' | { grep ${USER_NAME} || true; })

if [ -z "$USER_EXISTS" ]; then
    echo "$USER_SSHKEY" | ssh gerrit gerrit create-account ${USER_NAME} \
        -g \"Non-Interactive Users\"        \
        --email "${USER_MAIL}"              \
        --full-name \"${USER_FULLNAME}\"    \
        --ssh-key -
fi
