# SFCONFIG - Software Factory configuration management

## Install Software Factory on rhel-9

Only the mimimal arch is supported on rhel-9, the arch file will be copied on /etc/software-factory/arch.yaml during `ansible-playbook ansible/setup.yaml` step

* Register your system

`sh
subscription-manager register
`

* Install git, pip and ansible-core

`sh
dnf install git python3-pip ansible-core langpacks-en glibc-all-langpacks -y
`

* Install ansible galaxy collection

`sh
ansible-galaxy collection install ansible.posix community.general community.mysql
`

* Update crypto policies to allow old packages installation

`sh
update-crypto-policies --set DEFAULT:SHA1
`

* Clone sf-config repository as root user

`sh
git clone https://softwarefactory-project.io/r/software-factory/sf-config
`

* Setup sf-config

`sh
cd /root/sf-config
ansible-playbook ansible/setup.yaml
`

* install Software Factory
`sh
/usr/local/bin/sfconfig
`
## Ansible roles components

Each roles can define a meta/sfconfig.py file to create a Component class:

* argparse() method can expose command line argument,
  example: see the --zuul-merger parameter

* prepare() method can validate role requirements and define global vars,
  example: see the zuul-launcher prepare that automatically adds the logserver
           role when needed

* configure() method can be used to generate complex role parameters:
** Call add_mysql_database() to set mysql role vars to create a database
** Call generate_ssh_keys() to create ssh keys
** Convert sfconfig.yaml settings into role variables
** Render convenient variable such as internal_url
