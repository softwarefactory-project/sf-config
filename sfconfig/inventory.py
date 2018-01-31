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
    action = {'role_action': 'disable', 'erase': False}

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
    action = {'role_action': 'disable', 'erase': True}

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
    pb.append(host_play('all', 'upgrade', {'role_action': 'pre'}))

    # First turn off all component except gerrit and databases
    for host in args.inventory:
        roles = [role for role in host["roles"] if
                 role not in ("mysql", "zookeeper",
                              "gerrit", "hypervisor-oci")]
        pb.append(host_play(host, roles, {'role_action': 'disable',
                                          'erase': False}))

    # Upgrade repositories
    pb.append(host_play('install-server', 'repos', {'role_action': 'upgrade'}))

    # Turn off gerrit
    pb.append(host_play('gerrit', tasks={'service': {'name': 'gerrit',
                                                     'state': 'stopped'}}))

    # Install new release and update packages
    pb.append(host_play('all', 'upgrade', {'role_action': 'packages'}))

    # Start role upgrade
    action = {'role_action': 'upgrade'}
    pb.append(host_play('install-server', 'install-server', action))
    pb.append(host_play('all', 'base', action))
    for host in args.inventory:
        pb.append(host_play(host, host['roles'], action))


def install(args, pb):
    action = {'role_action': 'install'}
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
        play = host_play(host, params={'role_action': 'restore'})
        play['roles'] = []
        for role in host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'backup_src': '/var/lib/software-factory'
                                                '/backup/%s' % role})
        pb.append(play)

    pb.append(host_play('install-server',
                        tasks=notify_journald("recover ended")))


def setup(args, pb):
    action = {'role_action': 'setup'}
    # Setup install-server ssh keys
    pb.append(host_play('install-server', 'ssh', action))

    # Setup base role on all hosts
    for host in args.inventory:
        roles_action = {'role_action': 'setup', 'manage_etc_hosts': True}
        host_roles = ["postfix", "base", "monit"]
        if "hypervisor-oci" in host["roles"] and \
           args.glue.get("enable_insecure_slaves") is not True:
            # This host is running on isolated network
            host_roles = ["base"]
            roles_action['manage_etc_hosts'] = False
        pb.append(host_play(host, host_roles, roles_action))

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
    # The list of role to run update task
    roles_order = ["gerrit", "jenkins", "pages", "gerritbot",
                   "gateway", "managesf", "mirror", "repoxplorer",
                   "zuul", "nodepool", "zuul3", "nodepool3", "grafana"]
    # The extra list of host group to run fetch-config-repo
    roles_group = [
        "zuul-server", "zuul-merger",
        "nodepool-launcher", "nodepool-builder",
        "zuul3-scheduler", "zuul3-merger", "zuul3-executor", "zuul3-web",
        "nodepool3-launcher", "nodepool3-builder",
    ]
    pb.append(host_play(':'.join(roles_order + roles_group),
                        'repos', {'role_action': 'fetch_config_repo'}))

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

    # Update all components
    for host in args.inventory:
        host_roles = []
        for role in roles_order:
            if role in host["roles"]:
                host_roles.append(role)
        pb.append(host_play(host, host_roles, {'role_action': 'update'}))


def postconf(args, pb):
    for host in args.inventory:
        pb.append(host_play(host, host["roles"], {'role_action': 'postconf'}))


def enable_action(args):
    pb = []
    if not args.skip_populate_hosts:
        pb.append(host_play('install-server', 'ssh',
                            {'role_action': 'populate_hosts'}))
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
        config_update(args, pb)
        postconf(args, pb)
    else:
        playbook_name += "_nosetup"

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
        for host in args.glue["inventory"]:
            logfile = "/var/log/software-factory/testinfra.log"
            testinfra = ["testinfra", "-v", "--result-log=%s" % logfile]
            tests = []
            if "install-server" not in host["roles"]:
                testinfra.append("--connection=ssh")
                testinfra.append("--hosts=%s" % host["hostname"])
            for role in host["roles"]:
                if 'influxdb' or 'graphite-api' in role:
                    tests.append('telegraf')
                if role in testinfra_tests:
                    tests.append(role)
            if 'influxdb' or 'graphite-api' in role:
                tests.append('telegraf')
            if tests:
                for test in tests:
                    testinfra.append(testinfra_tests[test])
                pb.append(host_play('install-server', tasks={
                    'name': 'Validate deployment with testinfra: %s' % tests,
                    'command': " ".join(testinfra),
                    'register': 'result',
                    'until': 'result.rc == 0',
                    'retries': 60,
                    'delay': 1
                }))

    return playbook_name, pb


def enable_ara():
    try:
        import ara
        import ConfigParser
    except ImportError:
        return

    ara_cfg = "/var/lib/software-factory/ansible/ara.cfg"
    if not os.path.isfile(ara_cfg):
        ara_location = os.path.dirname(ara.__file__)
        ansiblecfg = ConfigParser.ConfigParser()
        ansiblecfg.read("/usr/share/sf-config/ansible/ansible.cfg")
        ansiblecfg.set("defaults", "callback_plugins",
                       "%s/plugins/callbacks" % ara_location)
        ansiblecfg.set("defaults", "action_plugins",
                       "%s/plugins/actions" % ara_location)
        ansiblecfg.set("defaults", "library",
                       "%s/plugins/modules" % ara_location)
        ansiblecfg.write(open(ara_cfg, "w"))
    os.environ["ANSIBLE_CONFIG"] = ara_cfg
    os.environ["ARA_LOG_FILE"] = ""
    os.environ["ARA_DIR"] = "/var/lib/software-factory/ansible/ara/"


def run(args):
    if args.disable or args.erase:
        playbook_name, playbook = disable_action(args)
    else:
        playbook_name, playbook = enable_action(args)

    playbook_path = "%s/%s.yml" % (args.ansible_root, playbook_name)
    write_playbook(playbook_path, playbook)
    os.environ["ANSIBLE_CONFIG"] = "%s/ansible/ansible.cfg" % args.share
    if not args.skip_apply:
        enable_ara()
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
        play = host_play(host, params={'role_action': 'get_logs'})
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
        play = host_play(host, params={'role_action': 'backup'})
        play['roles'] = []
        for role in host["roles"]:
            play['roles'].append({'role': "sf-%s" % role,
                                  'backup_dest': '/var/lib/software-factory'
                                                 '/backup/%s' % role})
        pb.append(play)


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
            if "gerrit" in host["roles"]:
                host["roles"].append("germqtt")

        # if influxdb role is in the arch, install telegraf
        if "influxdb" in args.glue["roles"]:
            if ("hypervisor-oci" not in host["roles"] or
                ("hypervisor-oci" in host["roles"] and
                 args.glue.get("enable_insecure_slaves") is True)):
                host["roles"].append("telegraf")

        if "gateway" in host["roles"] and \
           args.sfconfig['network']['use_letsencrypt']:
            host["roles"].insert(0, "lecm")

        # Check for conflicts
        for conflict in (("zuul3-merger", "zuul-merger")):
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
