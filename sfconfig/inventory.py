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
    if "install-server" in host.get("roles", []) or \
       host['hostname'] in ('localhost', 'install-server'):
        host_play['connection'] = 'local'
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
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role not in ("mysql", "install-server")]
        pb.append(host_play(host, host_roles, action))
    if 'influxdb' in args.glue['roles']:
        pb.append(host_play('all', 'telegraf', action))
    pb.append(host_play('mysql', 'mysql', action))
    pb.append(host_play('install-server', 'install-server', action))
    pb.append(host_play('all', 'base', action))


def erase(args, pb):
    prompt = "WARNING: this playbook will *DESTROY* software factory " \
             "data , press ENTER to continue or CTRL-C to abort"
    action = {'action': 'disable', 'erase': True}
    pb.append(host_play('localhost', tasks={
        'pause': {'prompt': prompt},
        'when': 'sfconfig_batch is not defined'}))
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role not in ("mysql", "install-server")]
        pb.append(host_play(host, host_roles, action))
    pb.append(host_play('mysql', 'mysql', action))
    pb.append(host_play('install-server', 'install-server', action))
    pb.append(host_play('all', 'base', action))
    # TODO: move this in base disable ?
    pb.append(host_play('all', tasks={
        'file': {'path': "{{ item }}",
                 'state': 'absent'},
        'with_items': [
            "/var/lib/software-factory/sql",
            "/var/lib/software-factory/state",
            "/var/lib/software-factory/.version",
            "/var/lib/software-factory/bootstrap-data/secrets.yaml",
            "/var/lib/software-factory/ansible"
        ]}))


def disable_action(args):
    pb = []
    playbook_name = "sfconfig"
    if args.disable:
        playbook_name += "_disable"
        disable(args, pb)
    elif args.erase:
        playbook_name += "_erase"
        erase(args, pb)
    return playbook_name, pb


def upgrade(args, pb):
    # Store current installed packages list
    pb.append(host_play('all', tasks={'name': 'Store installed packages list',
                                      'shell': 'rpm -qa | sort > '
                                               '/var/lib/software-factory/'
                                               'package_installed'}))

    # First turn off all component except gerrit
    for host in args.inventory:
        roles = [role for role in host["roles"] if
                 role not in ("mysql", "gerrit")]
        pb.append(host_play(host, roles, {'action': 'disable',
                                          'erase': False}))

    # Push config-repo changes now
    # TODO: move this in a role
    pb.append(host_play('localhost', tasks=[
        {'name': 'Ensure zuul-jobs exists',
         'file': {'path': '/root/config/jobs-zuul', 'state': 'directory'}},
        {'name': "Ensure defaults files are updated (prefixed by '_')",
         'template': {'src': "{{ item.src }}",
                      'dest': "/root/config/{{ item.dest }}"},
         'with_items': [
             {'src': '/usr/share/sf-config/templates/_macros.yaml.j2',
              'dest': 'jobs-zuul/_macros.yaml'},
             {'src': '/usr/share/sf-config/config-repo/jobs-zuul/_config.yaml',
              'dest': 'jobs-zuul/_config.yaml'},
             {'src': '/usr/share/sf-config/templates/_default_jobs.yaml.j2',
              'dest': 'jobs/_default_jobs.yaml'},
             {'src': '/usr/share/sf-config/config-repo/zuul/_layout.yaml',
              'dest': 'zuul/_layout.yaml'}
         ],
         'register': 'config_repo_status'},
        {'block': [
            {'name': 'Nothing to do (yet)',
             'command': '/bin/true'}],
         'when': 'sf_previous_version == "2.6"'},
        {'name': 'Push config-repo updates',
         'command': 'chdir=/root/config {{ item }}',
         'with_items': [
             'git add jobs-zuul/_macros.yaml jobs-zuul/_config.yaml',
             'git commit -a -m "Update default configuration '
             '(from {{ sf_previous_version }} to {{ sf_version }})"',
             'git push git+ssh://gerrit/config master',
         ]}
    ]))

    # Turn off gerrit
    pb.append(host_play('gerrit', tasks={'service': {'name': 'gerrit',
                                                     'state': 'stopped'}}))

    # Install new release and update packages
    # TODO: move this in a role
    pb.append(host_play('all', tasks=[
        {'name': 'Install new release repo',
         'yum': {
             'name': 'https://softwarefactory-project.io/repos/'
                     'sf-release-{{ sf_version }}.rpm',
             'state': 'present'
         },
         'when': 'sf_version != "master"'},
        {'name': 'Update packages',
         'yum': {
             'name': '*',
             'state': 'latest',
             'exclude': 'jenkins',
             'update_cache': 'yes',
             'disablerepo': '{{ yum_disable_repo|default(omit) }}',
             'enablerepo': '{{ yum_enable_repo|default(omit) }}'
         }}
    ]))

    # Start role upgrade
    action = {'action': 'upgrade'}
    pb.append(host_play('install-server', 'install-server', action))
    pb.append(host_play('all', 'base', action))
    for host in args.inventory:
        pb.append(host_play(host, host['roles'], action))


def install(args, pb):
    action = {'action': 'install'}
    roles = ['base']
    if 'influxdb' in args.glue['roles']:
        roles.append('telegraf')
    pb.append(host_play('all', roles, action))
    if args.sfconfig['network']['use_letsencrypt']:
        pb.append(host_play('gateway', 'lecm', action))
    for host in args.inventory:
        pb.append(host_play(host, host['roles'], action))


def recover(args, pb):
    pb.append(host_play('localhost', tasks=[
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

    pb.append(host_play('localhost', tasks=notify_journald("recover ended")))


def setup(args, pb):
    action = {'action': 'setup'}
    # Setup install-server ssh keys
    pb.append(host_play('localhost', 'ssh', action))

    # Setup sf-base role on all hosts
    roles = ['postfix', 'base', 'monit']
    if 'influxdb' in args.glue['roles']:
        roles.append('telegraf')
    pb.append(host_play('all', roles, action))

    # Setup sf-mysql role before all components
    pb.append(host_play('mysql', 'mysql', action))

    # Setup lecm if needed
    if args.sfconfig['network']['use_letsencrypt']:
        pb.append(host_play('gateway', 'lecm', action))

    # Setup all components
    for host in args.inventory:
        host_roles = [role for role in host["roles"] if
                      role != 'mysql']
        pb.append(host_play(host, host_roles, action))

    # Create config projects
    tasks = [{'include': "{{ sf_tasks_dir }}/create_config-repo.yml"}]
    if 'zuul3' in args.glue['roles']:
        tasks.append({'include': "{{ sf_tasks_dir }}/create_zuul-jobs.yml"})
    pb.append(host_play('localhost', tasks=tasks, params=action))


def config_update(args, pb):
    # Check config repo HEAD and update /root/config copy for each services
    pb.append(host_play('localhost', tasks={
        'name': 'Get config sha1',
        'command': 'git ls-remote -h http://{{ fqdn }}/r/config.git',
        'register': 'configsha'
    }))
    pb.append(host_play('all', tasks={
        'include': '{{ sf_tasks_dir }}/update_configrepo.yaml'
    }))
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
    pb.append(host_play('localhost', tasks={
        'include': '{{ sf_tasks_dir }}/ssh_populate_known_hosts.yml'}))
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
    pb.append(host_play('localhost', tasks={
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
                pb.append(host_play('localhost', tasks={
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
    # TODO: move this into a role
    tasks = [
        {'file': {'path': '/root/sf-logs', 'state': 'absent'},
         'name': 'Cleanup sf-logs directory'},
        {'file': {'mode': 448, 'path': '/root/sf-logs', 'state': 'directory'},
         'name': 'Create sf-logs directory'},
        {'ignore_errors': True,
         'name': 'Copy the config repo',
         'synchronize': {'dest': '/root/sf-logs/config-repo',
                         'rsync_opts': '--exclude .git',
                         'src': '/root/config'}},
        {'ignore_errors': True,
         'name': 'Get config repo git logs',
         'shell': 'cd /root/config && git log --name-only > '
         '/root/sf-logs/config-repo.git.log'},
        {'ignore_errors': True,
         'name': 'Synchronize sf data',
         'synchronize': {'dest': "{{ item.dest }}",
                         'rsync_opts': '--exclude .git',
                         'src': "{{ item.src }}"},
         'with_items': [{'dest': '/root/sf-logs/etc_software-factory',
                         'src': '/etc/software-factory'},
                        {'dest': '/root/sf-logs/var_ansible',
                         'src': '/var/lib/software-factory/ansible'},
                        {'dest': '/root/sf-logs/sf-bootstrap-data',
                         'src': '/var/lib/software-factory/bootstrap-data'},
                        {'dest': '/root/sf-logs/log_config-updates',
                         'src': '/var/log/software-factory'}]}
    ]
    for role in args.glue["roles"]:
        tasks.append({'name': 'Create %s log storage directory' % role,
                      'file': {'path': '/root/sf-logs/%s' % role,
                               'state': 'directory'}})
    pb.append(host_play('localhost', tasks=tasks))
    pb.append(host_play('all', tasks=[
        {'name': 'Check for unconfined process',
         'shell': 'ps auxZ | grep -i "unconfin" '
         ' > /var/log/audit/unconfined_process.txt'},
        {'name': 'Fetch system logs',
         'ignore_errors': True,
         'fetch': {
             'src': '{{ item }}',
             'dest': '/root/sf-logs'
         },
         'with_items': [
             '/var/log/messages',
             '/var/log/audit/audit.log',
             '/var/log/audit/unconfined_process.txt',
             '/var/log/upgrade-bootstrap.log',
             '/var/log/cloud-init.log',
             '/var/log/cloud-init-output.log',
         ]}]))

    for host in args.inventory:
        play = host_play(host, params={'action': 'get_logs'})
        play['roles'] = []
        for role in host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'log_dest': '/root/sf-logs/%s' % role})
        pb.append(play)


def backup(args, pb):
    # Create local backup directory
    pb.append(host_play('localhost', tasks=[
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
    pb.append(host_play('localhost', tasks=[
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
    new = template.render(data) + "\n"
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

    # Check for conflicts
    for conflict in (("zuul3", "zuul")):
        for host in arch["inventory"]:
            if conflict[0] in host["roles"] and conflict[1] in host["roles"]:
                raise RuntimeError("%s: can't install both %s and %s" % (
                    host["hostname"], conflict[0], conflict[1]
                ))
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
