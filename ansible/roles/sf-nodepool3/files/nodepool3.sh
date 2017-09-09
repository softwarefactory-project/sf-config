#!/bin/sh

exec scl enable rh-python35 -- /opt/rh/rh-python35/root/bin/nodepool -c /etc/opt/rh/rh-python35/nodepool/nodepool.yaml $*
