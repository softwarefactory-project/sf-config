#!/bin/sh

exec scl enable rh-python35 -- /opt/rh/rh-python35/root/bin/zuul -c /etc/opt/rh/rh-python35/zuul/zuul.conf $*
