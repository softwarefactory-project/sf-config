#!/bin/sh

exec scl enable rh-python35 -- /opt/rh/rh-python35/root/bin/nodepool \
     -s /etc/opt/rh/rh-python35/nodepool/secure.conf \
     -c /etc/opt/rh/rh-python35/nodepool/nodepool.yaml $*
