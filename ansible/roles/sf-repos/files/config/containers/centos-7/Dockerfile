# Copyright (C) 2019 Red Hat
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

FROM registry.centos.org/centos:7

# Zuul minimal package
RUN yum install -y sudo rsync git traceroute iproute python3-setuptools python3-pip rpm-build python3-rpm-macros

# Zuul except /bin/pip to be available
RUN ln -sf /bin/pip3 /bin/pip && /bin/pip3 install --user "tox>=3.8.0"

# Install base Python linter for the demo project
RUN /bin/pip install flake8 yamllint

# Zuul uses revoke-sudo. We can simulate that by moving the default sudoers to zuul
# And this will prevent root from using sudo when the file is removed by revoke-sudo
RUN mv /etc/sudoers /etc/sudoers.d/zuul && grep includedir /etc/sudoers.d/zuul > /etc/sudoers && sed -e 's/.*includedir.*//' -i /etc/sudoers.d/zuul && chmod 440 /etc/sudoers

# Create fake zuul users
RUN echo "zuul:x:0:0:root:/root:/bin/bash" >> /etc/passwd

# Enable root local bin
ENV PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
WORKDIR /root
