#!/bin/sh

ACTION=${SSH_ORIGINAL_COMMAND:-sf_configrepo_update}

export ANSIBLE_CONFIG=/usr/share/sf-config/ansible/ansible.cfg

case $ACTION in
    sf_configrepo_update)
        exec ansible-playbook /var/lib/software-factory/ansible/sf_configrepo_update.yml &> /var/log/software-factory/configrepo_update.log
        ;;
    sf_mirror_update)
        exec ansible-playbook -v /usr/share/sf-config/ansible/roles/sf-mirror/files/update_playbook.yml &> /var/log/software-factory/mirror_update.log
        ;;
    sf_backup)
        exec ansible-playbook -v /var/lib/software-factory/ansible/sf_backup.yml &> /var/log/software-factory/backup.log
        ;;
    sf_restore)
        exec ansible-playbook -v /var/lib/software-factory/ansible/sf_restore.yml &> /var/log/software-factory/restore.log
        ;;
    *)
        echo "NotImplemented"
        exit -1
esac
