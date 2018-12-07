#!/bin/bash
set -ex

yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm
yum install -y python-ecdsa python-lockfile mock
yum remove -y epel-release
