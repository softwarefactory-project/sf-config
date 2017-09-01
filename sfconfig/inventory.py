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

import copy
import os
import yaml

from jinja2 import FileSystemLoader
from jinja2.environment import Environment

import sfconfig.utils


def write_playbook(playbook_path, playbook):
    if os.path.exists(playbook_path):
        current = open(playbook_path).read()
    else:
        current = ""
    new = yaml.dump(playbook, default_flow_style=False)
    if new != current:
        with open(playbook_path, "w") as out:
            out.write(new)
        print("[+] Wrote %s" % playbook_path)


def notify_journald(msg):
    return {'name': 'Signal journald', 'command': 'logger sfconfig %s' % msg}


def host_play(host, roles=[], params={}, tasks=[]):
    """Generate a ansible host play block"""
    if not isinstance(host, dict):
        host = {'hostname': host}
    if not isinstance(roles, list):
        roles = [roles]
    if not isinstance(tasks, list):
        tasks = [tasks]

    host_play = {'hosts': host['hostname']}
    if roles:
        host_play['roles'] = []
        for role in roles:
            host_play['roles'].append('sf-%s' % role)
    if tasks:
        host_play['tasks'] = tasks
    if host.get('params', None):
        host_play['vars'] = copy.deepcopy(host['params'])
    if params:
        host_play.setdefault('vars', {}).update(params)
    return host_play


def disable(args, pb):
    action = {'action': 'disable', 'erase': False}

    # Disable all but mysql and install-server
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role not in ("mysql", "install-server")]
        pb.append(host_play(host, host_roles, action))

    # Then disable mysql and install-server
    pb.append(host_play('mysql', 'mysql', action))
    pb.append(host_play('install-server', 'install-server', action))

    # Last disable base from all
    pb.append(host_play('all', 'base', action))


def erase(args, pb):
    action = {'action': 'disable', 'erase': True}

    # First get confirmation
    prompt = "WARNING: this playbook will *DESTROY* software factory " \
             "data , press ENTER to continue or CTRL-C to abort"
    pb.append(host_play('install-server', tasks={
        'pause': {'prompt': prompt},
        'when': 'sfconfig_batch is not defined'}))

    # Erase all but mysql and install-server
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role not in ("mysql", "install-server")]
        pb.append(host_play(host, host_roles, action))

    # Then erase mysql and install-server
    pb.append(host_play('mysql', 'mysql', action))
    pb.append(host_play('install-server', 'install-server', action))

    # Last erase base from all
    pb.append(host_play('all', 'base', action))


def disable_action(args):
    pb = []
    playbook_name = "sfconfig"
    if args.erase:
        playbook_name += "_erase"
        erase(args, pb)
    elif args.disable:
        playbook_name += "_disable"
        disable(args, pb)
    return playbook_name, pb


def upgrade(args, pb):
    # Call pre upgrade task
    pb.append(host_play('all', 'upgrade', {'action': 'pre'}))

    # First turn off all component except gerrit
    for host in args.inventory:
        roles = [role for role in host["roles"] if
                 role not in ("mysql", "gerrit")]
        pb.append(host_play(host, roles, {'action': 'disable',
                                          'erase': False}))

    # Upgrade repositories
    pb.append(host_play('install-server', 'repos', {'action': 'upgrade'}))

    # Turn off gerrit
    pb.append(host_play('gerrit', tasks={'service': {'name': 'gerrit',
                                                     'state': 'stopped'}}))

    # Install new release and update packages
    pb.append(host_play('all', 'upgrade', {'action': 'packages'}))

    # Start role upgrade
    action = {'action': 'upgrade'}
    pb.append(host_play('install-server', 'install-server', action))
    pb.append(host_play('all', 'base', action))
    for host in args.inventory:
        pb.append(host_play(host, host['roles'], action))


def install(args, pb):
    action = {'action': 'install'}
    pb.append(host_play('all', 'base', action))
    for host in args.inventory:
        pb.append(host_play(host, host['roles'], action))


def recover(args, pb):
    pb.append(host_play('install-server', tasks=[
        notify_journald("recover started"),
        {'name': 'Ensure role directory exists',
         'file': {
             'path': '/var/lib/software-factory/backup/{{ item }}',
             'state': 'directory'
         },
         'with_items': [role for role in args.glue['roles']]}
    ]))

    # Start mysql
    pb.append(host_play('mysql', tasks=[
        {'yum': {
            'name': 'mariadb-server',
            'state': 'present',
            'disablerepo': '{{ yum_disable_repo|default(omit) }}',
            'enablerepo': '{{ yum_enable_repo|default(omit) }}',
        }},
        {'service': {'name': 'mariadb', 'state': 'started'}}
    ]))

    # Call restore task
    for host in args.inventory:
        play = host_play(host, params={'action': 'restore'})
        play['roles'] = []
        for role in host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'backup_src': '/var/lib/software-factory'
                                                '/backup/%s' % role})
        pb.append(play)

    pb.append(host_play('install-server',
                        tasks=notify_journald("recover ended")))


def setup(args, pb):
    action = {'action': 'setup'}
    # Setup install-server ssh keys
    pb.append(host_play('install-server', 'ssh', action))

    # Setup base role on all hosts
    pb.append(host_play('all', ['postfix', 'base', 'monit'], action))

    # Setup mysql role before all components
    pb.append(host_play('mysql', 'mysql', action))

    # Setup all components except mysql
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role != 'mysql']
        pb.append(host_play(host, host_roles, action))

    # Create config projects
    pb.append(host_play('install-server', 'repos', action))


def config_update(args, pb):
    # Check config repo HEAD and update /root/config copy for each services
    pb.append(host_play('install-server', tasks={
        'name': 'Get config sha1',
        'command': 'git ls-remote -h https://{{ fqdn }}/r/config.git',
        'register': 'configsha'
    }))
    pb.append(host_play('all', 'repos', {'action': 'fetch_config_repo'}))

    role_order = ["gerrit", "jenkins", "pages", "gerritbot",
                  "zuul", "nodepool", "zuul3", "nodepool3"]
    for role in args.glue["roles"]:
        if role not in role_order:
            role_order.append(role)

    # Update all components
    for host in args.inventory:
        host_roles = []
        for role in role_order:
            if role in host["roles"]:
                host_roles.append(role)
        pb.append(host_play(host, host_roles, {'action': 'update'}))

    # Call resources apply
    pb.append(host_play('managesf', tasks=[
        {'name': 'Exec resources apply',
         'command': '/usr/local/bin/resources.sh apply',
         'register': 'output',
         'ignore_errors': 'yes'},
        {'debug': {'msg': '{{ output.stdout_lines }}'}},
        {'fail': {'msg': 'Resources apply failed {{ output.rc }}'},
         'when': 'output.rc != 0'}
    ]))


def postconf(args, pb):
    for host in args.inventory:
        pb.append(host_play(host, host["roles"], {'action': 'postconf'}))


def enable_action(args):
    pb = []
    pb.append(host_play('install-server', 'ssh', {'action': 'populate_hosts'}))
    playbook_name = "sfconfig"
    if args.upgrade:
        playbook_name += "_upgrade"
        upgrade(args, pb)
    if not args.skip_install:
        install(args, pb)
    else:
        playbook_name += "_noinstall"
    if args.recover:
        playbook_name += "_recover"
        recover(args, pb)
    if not args.skip_setup:
        setup(args, pb)
    else:
        playbook_name += "_nosetup"

    config_update(args, pb)
    postconf(args, pb)

    # Store deployed version to be used by upgrade playbook
    pb.append(host_play('install-server', tasks={
        'name': 'Write current version',
        'copy': {
            'dest': "/var/lib/software-factory/.version",
            'content': "{{ sf_version }}"
        }
    }))

    if not args.skip_test:
        testinfra_tests = sfconfig.utils.list_testinfra()
        for host in args.sfarch["inventory"]:
            testinfra = ["testinfra"]
            to_run = False
            if "install-server" not in host["roles"]:
                testinfra.append("--connection=ssh")
                testinfra.append("--hosts=%s" % host["hostname"])
            for role in host["roles"]:
                if role in testinfra_tests:
                    testinfra.append(testinfra_tests[role])
                    to_run = True
            if to_run:
                pb.append(host_play('install-server', tasks={
                    'name': 'Validate deployment with testinfra',
                    'command': " ".join(testinfra),
                    'register': 'result',
                    'until': 'result.rc == 0',
                    'retries': 60,
                    'delay': 1
                }))

    return playbook_name, pb


def run(args):
    if args.disable or args.erase:
        playbook_name, playbook = disable_action(args)
    else:
        playbook_name, playbook = enable_action(args)

    playbook_path = "%s/%s.yml" % (args.ansible_root, playbook_name)
    write_playbook(playbook_path, playbook)
    os.environ["ANSIBLE_CONFIG"] = "%s/ansible/ansible.cfg" % args.share
    if not args.skip_apply:
        sfconfig.utils.execute(["ansible-playbook", playbook_path])


def get_logs(args, pb):
    # Create /root/sf-logs directories
    tasks = [
        {'file': {'path': '/root/sf-logs', 'state': 'absent'},
         'name': 'Cleanup sf-logs directory'},
        {'file': {'mode': 448, 'path': '/root/sf-logs', 'state': 'directory'},
         'name': 'Create sf-logs directory'},
    ]
    for role in args.glue["roles"]:
        tasks.append({'name': 'Create %s log storage directory' % role,
                      'file': {'path': '/root/sf-logs/%s' % role,
                               'state': 'directory'}})
    pb.append(host_play('install-server', tasks=tasks))

    for host in args.inventory:
        play = host_play(host, params={'action': 'get_logs'})
        play['roles'] = []
        for role in ["base"] + host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'log_dest': '/root/sf-logs/%s' % role})
        pb.append(play)


def backup(args, pb):
    # Create local backup directory
    pb.append(host_play('install-server', tasks=[
        {'name': "Create backup directory",
         'file': {'path': '/var/lib/software-factory/backup',
                  'state': 'directory',
                  'mode': '0700'}},
        {'file': {'path': "/var/lib/software-factory/backup/{{ item }}",
                  'state': 'directory'},
         'with_items': list(args.glue['roles'])}]))

    # Call backup task
    for host in args.inventory:
        play = host_play(host, params={'action': 'backup'})
        play['roles'] = []
        for role in host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'backup_dest': '/var/lib/software-factory'
                                                 '/backup/%s' % role})
        pb.append(play)

    # Generate backup file
    pb.append(host_play('install-server', tasks=[
        {'name': "Generate backup file",
         'command': "chdir=/var/lib/software-factory/backup/ "
                    "tar czpf /var/lib/software-factory/backup.tar.gz ."},
        {'name': "Copy backup to managesf",
         'command': 'scp /var/lib/software-factory/backup.tar.gz '
                    '{{ managesf_host }}:/var/lib/managesf/sf_backup.tar.gz'}
    ]))


def render_template(dest, template, data):
    if os.path.exists(dest):
        current = open(dest).read()
    else:
        current = ""
    loader = FileSystemLoader(os.path.dirname(template))
    env = Environment(trim_blocks=True, loader=loader)
    template = env.get_template(os.path.basename(template))
    new = template.render(data)
    if new[-1] != "\n":
        new += "\n"
    if new != current:
        with open(dest, "w") as out:
            out.write(new)
        print("[+] Wrote %s" % dest)


def generate(args):
    # Copy the original arch to add host params
    arch = copy.deepcopy(args.sfarch)

    # Adds playbooks to architecture
    for host in arch["inventory"]:
        # Host params are generic roles parameters
        host["params"] = {'host_public_url': host['public_url']}

        # This method handles roles such as zuul-merger that are in fact the
        # zuul role with the zuul_services argument set to "merger"
        def ensure_role_services(role_name, meta_names):
            # Ensure base role exists for metarole
            for meta_name in meta_names:
                # Add role services for meta role
                service_name = "%s-%s" % (role_name, meta_name)
                if service_name in host["roles"]:
                    host["params"].setdefault(
                        "%s_services" % role_name, []).append(
                            service_name.replace('3', ''))
                    # Remove meta-name role
                    host["roles"] = list(filter(
                        lambda x: x != service_name, host["roles"]))
                    # Add base role to host
                    if role_name not in host["roles"]:
                        host["roles"].append(role_name)
                    if role_name not in args.glue["roles"]:
                        args.glue["roles"].setdefault(role_name, []).append(
                            host)

        ensure_role_services("nodepool", ["launcher", "builder"])
        ensure_role_services("zuul", ["server", "merger", "launcher"])
        ensure_role_services("nodepool3", ["launcher", "builder"])
        ensure_role_services("zuul3", ["scheduler", "merger", "executor",
                                       "web"])

        # if firehose role is in the arch, install publishers where needed
        if "firehose" in args.glue["roles"]:
            if "zuul" in host["roles"] or \
               "nodepool" in host["roles"] or \
               "zuul3" in host["roles"]:
                host["roles"].append("ochlero")
            if "gerrit" in host["roles"]:
                host["roles"].append("germqtt")

        # if influxdb role is in the arch, install telegraf
        if "influxdb" in args.glue["roles"]:
            host["roles"].append("telegraf")

        if "gateway" in host["roles"] and \
           args.sfconfig['network']['use_letsencrypt']:
            host["roles"].insert(0, "lecm")

    if 'hydrant' in args.glue["roles"] and \
       "firehose" not in args.glue["roles"]:
        raise RuntimeError("'hydrant' role needs 'firehose'")
    if 'hydrant' in args.glue["roles"] and \
       'elasticsearch' not in args.glue["roles"]:
        raise RuntimeError("'hydrant' role needs 'elasticsearch'")

    templates = "%s/templates" % args.share

    # Generate inventory
    arch["roles"] = args.glue["roles"]
    arch["hosts_file"] = args.glue["hosts_file"]
    render_template("%s/hosts" % args.ansible_root,
                    "%s/inventory.j2" % templates,
                    arch)

    # Generate playbooks
    args.inventory = arch["inventory"]
    for playbook_name, generator in (
            ("sf_configrepo_update", config_update),
            ("get_logs", get_logs),
            ("sf_backup", backup),
            ("sf_erase", erase)):
        playbook_path = "%s/%s.yml" % (args.ansible_root, playbook_name)
        playbook = []
        generator(args, playbook)
        write_playbook(playbook_path, playbook)

    # Generate /etc/hosts file
    render_template("/etc/hosts",
                    "%s/etc-hosts.j2" % templates,
                    arch)
