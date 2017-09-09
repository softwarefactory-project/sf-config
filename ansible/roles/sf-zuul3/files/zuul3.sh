#!/bin/sh

scl enable rh-python35 -- zuul -c /etc/opt/rh/rh-python35/zuul/zuul.conf $*
