#!/bin/bash
curl -o sf-master.qcow2 https://cloud.centos.org/centos/7/images/CentOS-7-x86_64-GenericCloud.qcow2
sudo yum install -y yum libguestfs-tools
virt-customize -a sf-master.qcow2 --selinux-relabel \
               --run-command "yum install -y https://softwarefactory-project.io/repos/sf-release-master.rpm" \
               --run-command "yum update -y" \
               --run-command "yum install --downloadonly sf-config --downloaddir=/tmp/" \
               --run-command "yum install -y /tmp/sf-config*" \
               --run-command "sed -i '/populate_hosts/d' /usr/lib/python2.7/site-packages/sfconfig/inventory.py" \
               --run-command "sed -i '/    config_update(args, pb)/d' /usr/lib/python2.7/site-packages/sfconfig/inventory.py" \
               --run-command "sed -i '/    postconf(args, pb)/d' /usr/lib/python2.7/site-packages/sfconfig/inventory.py" \
               --run-command "mkdir /dev/shm && mount -t tmpfs shmfs /dev/shm" \
               --run-command "sfconfig --skip-setup --skip-test --arch /usr/share/sf-config/refarch/allinone.yaml" \
               --run-command "rm -rf /var/lib/software-factory/*" \
               --run-command "yum reinstall -y /tmp/sf-config*"
