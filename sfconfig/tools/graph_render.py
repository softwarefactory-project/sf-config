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

import argparse
import urllib
import json
import os
import yaml

import sfconfig.utils


#############################
# Influxdb query management #
#############################
CONTINOUS_QUERY = {
    'zuul.all_jobs': {
        'measurement': '/zuul.tenant.*.pipeline.*.all_jobs/',
    },
}
NODE_STATUS = ("building", "ready", "in-use", "used",
               "deleting", "hold", "failed")
for node_status in NODE_STATUS:
    CONTINOUS_QUERY['nodepool.all_providers.%s' % node_status] = {
        'measurement': '/nodepool.provider.*.nodes.%s/' % node_status}


def update_cq_action(args):
    '''Update influx db continuous query, return 4 on changed'''
    if args.influxdb_host is None or args.influxdb_password is None:
        sfconfig.utils.fail("Host and password is required")
    influx_cmd = ['influx', '-ssl', '-unsafeSsl', '-host', args.influxdb_host,
                  '-port', '8086', '-username', 'admin', '-password',
                  args.influxdb_password, '-database', 'telegraf', '-execute']
    queries = sfconfig.utils.pread(
        influx_cmd + ["SHOW CONTINUOUS QUERIES"]).split('\n')
    changed = False
    for cq, cq_data in CONTINOUS_QUERY.items():
        cmd = 'CREATE CONTINUOUS QUERY "qc_%s" ON telegraf' % cq
        cmd += ' RESAMPLE FOR %s' % cq_data.get('resample_time', '30s')
        cmd += ' BEGIN SELECT %s(value) AS value' % cq_data.get('function',
                                                                'sum')
        cmd += ' INTO "%s"' % cq
        cmd += ' FROM %s' % cq_data['measurement']
        cmd += ' GROUP BY time(%s)' % cq_data.get('time', '30s')
        cmd += ' fill(%s)' % cq_data.get('resample_fill', '0')
        cmd += ' END'
        to_create = True
        for query in queries:
            if query.startswith("qc_%s " % cq):
                # Query name already exists, check if it needs update
                query = query.split(None, 1)[1]
                # Fix query creation command to match show command output
                qmd = cmd.replace("INTO ", "INTO telegraf.autogen.")
                qmd = qmd.replace("FROM ", "FROM telegraf.autogen.")
                if query == qmd:
                    to_create = False
                else:
                    # ALTER doesn't exists, we need to delete the previous one
                    print("Removing old %s" % cq)
                    sfconfig.utils.execute(influx_cmd + [
                        'DROP CONTINUOUS QUERY "qc_%s" ON "telegraf"' % cq])
                break
        if to_create:
            changed = True
            print("Adding %s" % cq)
            sfconfig.utils.execute(influx_cmd + [cmd])
    return 4 if changed else 0


#######################
# Grafyaml generation #
#######################
def dashboard(name, description):
    desc = "**%s**\n\n%s" % (
        description,
        'This dashboard is automatically generated by sfconfig.'
        ' If you would like to make changes, check the graph_render module'
    )
    return {
        'title': name,
        'rows': [{
            'title': 'Description',
            'height': '100px',
            'panels': [{
                'title': 'Description',
                'type': 'text',
                'content': desc,
                }]
            }
        ]}


def row(title, height='150px', show_title=True):
    return {
        'title': title.capitalize(),
        'height': height,
        'showTitle': show_title,
        'panels': []}


def single_stat(title, measurement, span=2, tags=True):
    stat = {
        'title': title.capitalize(),
        'span': span,
        'sparkline': {'full': True, 'show': True},
        'targets': [{
            'groupBy': [{'type': 'time', 'params': ['$__interval']},
                        {'type': 'fill', 'params': ['0']}],
            'measurement': measurement,
            'orderByTime': 'ASC',
            'resultFormat': 'time_series',
            'select': [[{'type': 'field', 'params': ['value']},
                        {'type': 'distinct', 'params': []}]],
        }],
        'type': 'singlestat',
        'valueName': 'current',
    }
    if tags:
        for target in stat['targets']:
            target['tags'] = [{'key': 'metric_type', 'operator': '=',
                               'value': 'gauge'}]
    return stat


def graph(title, metrics, span=4, interval='$__interval', scale=None,
          stack=False, seriesOverrides=None, tooltip=None):
    targets = []
    for metric in metrics:
        if not metric.get('alias'):
            metric['alias'] = metric['m'].split('.')[-1].replace(
                '/', '').replace('_', ' ').capitalize()
        select = [
            {'type': 'field', 'params': ['value']},
            {'type': 'distinct', 'params': []},
        ]
        if scale:
            select.append({'type': 'math', 'params': [scale]})
        targets.append({
            'groupBy': [{'type': 'time', 'params': [interval]},
                        {'type': 'fill', 'params': ['0']}],
            'measurement': metric['m'],
            'alias': metric['alias'],
            'orderByTime': 'ASC',
            'resultFormat': 'time_series',
            'select': [select],
            'tags': [{'key': 'metric_type',
                      'operator': '=',
                      'value': metric.get('type', 'gauge')}]
        })
    g = {
        'title': title.capitalize(),
        'span': span,
        'targets': targets,
        'type': 'graph',
        'yaxes': [{"min": 0}, {"min": 0}]
    }
    if stack:
        g['stack'] = True
    if seriesOverrides:
        g['seriesOverrides'] = [{'alias': seriesOverrides, 'stack': False}]
    if tooltip:
        g['tooltip'] = {'value_type': tooltip}
    return g


def zuul_dashboard(args):
    d = dashboard("Zuul Status", "The Zuul service metrics")
    for tenant in args.tenants:
        tenant_row = row("%s's pipelines" % tenant['name'].capitalize())
        for pipeline in tenant['pipelines']:
            span = 3 if pipeline in ("check", "gate") else 2
            tenant_row['panels'].append(single_stat(
                pipeline,
                'zuul.tenant.%s.pipeline.%s.current_changes' % (
                    tenant['name'], pipeline),
                span))
        d['rows'].append(tenant_row)
    global_row = row("Global stats", height="250px")
    global_row["panels"].append(graph(
        'Jobs Launched (per Hour)',
        [{'m': '/zuul.tenant.*.pipeline.*.all_jobs/', 'type': 'counter'}],
        interval='1h'))
    if args.enable_logstash == 'true':
        global_row["panels"].append(graph(
            'Logstash Job Queue',
            [{'m': 'logstash.geard.queue.running'},
             {'m': 'logstash.geard.queue.waiting'},
             {'m': 'logstash.geard.queue.total'}]))
    global_row["panels"].append(graph(
        'Node Requests',
        [{'m': 'zuul.nodepool.current_requests', 'alias': 'Requests'}]))
    global_row["panels"].append(graph(
        'Job Queue',
        [{'m': 'zuul.geard.queue.running'},
         {'m': 'zuul.geard.queue.waiting'},
         {'m': 'zuul.geard.queue.total'}]))
    global_row["panels"].append(graph(
        'Gerrit Events',
        [{'m': 'zuul.event.gerrit.comment-added', 'type': 'counter'},
         {'m': 'zuul.event.gerrit.patchset-created', 'type': 'counter'},
         {'m': 'zuul.event.gerrit.change-merged', 'type': 'counter'}],
        interval='1h'))
    global_row["panels"].append(graph(
        'Test Nodes',
        [{'m': 'nodepool.nodes.building'},
         {'m': 'nodepool.nodes.ready'},
         {'m': 'nodepool.nodes.in-use'},
         {'m': 'nodepool.nodes.used'},
         {'m': 'nodepool.nodes.deleting'}, ],
        stack=True,
        seriesOverrides='Max',
        tooltip='individual'))
    d["rows"].append(global_row)
    executors_row = row("Executors", height="250px")
    executors_row["panels"].append(graph(
        "Executors",
        [{"m": "zuul.executors.online"}, {"m": "zuul.executors.accepting"}],
        span=6))
    executors_row["panels"].append(graph(
        "Executors Queue",
        [{"m": "zuul.executors.jobs_queued"},
         {"m": "zuul.executors.jobs_running"}],
        span=6))
    executors_row["panels"].append(graph(
        "Starting Builds",
        [{"m": "/zuul.executor.*.starting_builds/", 'alias': '$2'}],
        span=6))
    executors_row["panels"].append(graph(
        "Running Builds",
        [{"m": "/zuul.executor.*.running_builds/", 'alias': '$2'}],
        span=6))
    executors_row["panels"].append(graph(
        "Load Average",
        [{"m": "/zuul.executor.*.load_average/", 'alias': '$2'}],
        scale="/ 100",
        span=6))
    executors_row["panels"].append(graph(
        "Available RAM",
        [{"m": "/zuul.executor.*.pct_available_ram/", 'alias': '$2'}],
        scale="/ 100",
        span=6))
    d["rows"].append(executors_row)
    mergers_row = row("Mergers", height="250px")
    mergers_row["panels"].append(graph(
        "Mergers", [{"m": "zuul.mergers.online"}], span=6))
    mergers_row["panels"].append(graph(
        "Merger Queue", [
            {"m": "zuul.mergers.jobs_queued"},
            {"m": "zuul.mergers.jobs_running"}], span=6))
    d["rows"].append(mergers_row)
    return d


def nodepool_dashboard(args):
    d = dashboard("Nodepool Status", "The Nodepool service metrics")
    nodes_row = row("Nodes", height="150px")
    for status in NODE_STATUS:
        nodes_row["panels"].append(single_stat(
            status,
            '/nodepool.all_providers.%s/' % status,
            tags=False
            ))
    d["rows"].append(nodes_row)
    images_row = row("Images", height="320px")
    for status in ("building", "ready", "in-use", "deleting"):
        images_row["panels"].append(graph(
            status,
            [{"m": "/nodepool.label.*.%s/" % status, 'alias': '$2'}],
            span=3))
    d["rows"].append(images_row)
    launch_row = row("Launches", height="250px")
    # TODO
    d["rows"].append(launch_row)
    return d


def provider_dashboard(args, provider):
    d = dashboard("Provider - %s" % provider["name"],
                  "The Nodepool provider %s metrics" % provider["name"])
    nodes_row = row("Nodes", height="150px")
    for status in NODE_STATUS:
        nodes_row["panels"].append(single_stat(
            status,
            '/nodepool.provider.%s.nodes.%s/' % (provider["name"], status)))
    d["rows"].append(nodes_row)
    if provider["driver"] == "openstack":
        api_row = row("API Operations")
        for name, metric in (("Create Server", "ComputePostServers"),
                             ("Get Server", "ComputeGetServersDetail")):
            api_row["panels"].append(graph(
                name, [{"m": "timers.nodepool.task.%s.%s" % (
                    provider["name"], metric)}],
                span=4))
        d["rows"].append(api_row)
    return d


def update_grafyaml_action(args):
    '''Update grafyaml file, return 4 on changed'''
    if args.zuul_url is None or args.config_dir is None:
        sfconfig.utils.fail("Zuul url and config dir is required")
    args.tenants = get_tenants(args.zuul_url)
    args.providers = get_providers(args.config_dir)
    data = {
        "_zuul.yaml": zuul_dashboard(args),
        "_nodepool.yaml": nodepool_dashboard(args)
    }
    for provider in args.providers:
        data["_nodepool-%s.yaml" % provider["name"]] = provider_dashboard(
            args, provider)
    changed = False
    for name, data in data.items():
        content = yaml.safe_dump({'dashboard': data},
                                 default_flow_style=False)
        graf_file = os.path.join(args.config_dir, "metrics", name)
        if os.path.exists(graf_file) and open(graf_file).read() == content:
            continue
        changed = True
        open(graf_file, "w").write(content)
        print("%s: updated content" % graf_file)
    return 4 if changed else 0


############################
# Deployment configuration #
############################
def get_tenants(zuul_url):
    result = []
    tenants_url = urllib.urlopen("%s/tenants.json" % zuul_url)
    tenants = json.loads(tenants_url.read())
    for tenant in tenants:
        tenant_data = {"name": tenant["name"], "pipelines": []}
        tenant_url = urllib.urlopen(
            "%s/%s/pipelines.json" % (zuul_url, tenant["name"]))
        pipelines = json.loads(tenant_url.read())
        for pipeline in pipelines:
            tenant_data["pipelines"].append(pipeline["name"])
        result.append(tenant_data)
    return result


def get_providers(config_dir):
    result = []
    nodepool_conf = sfconfig.utils.yaml_merge_load(os.path.join(config_dir,
                                                                "nodepool"))
    for provider in nodepool_conf["providers"]:
        result.append({"name": provider["name"], "driver": provider["driver"]})
    return result


#########
# Usage #
#########
def main():
    p = argparse.ArgumentParser(
        description="Generate dynamic grafyaml dashboard")
    p.add_argument("--influxdb-host")
    p.add_argument("--influxdb-password")
    p.add_argument("--zuul-url")
    p.add_argument("--config-dir")
    p.add_argument("--output-dir")
    p.add_argument("--enable-logstash", default='false')
    p.add_argument("action", choices=("update-cq", "update-grafyaml"))
    args = p.parse_args()
    if args.action == "update-cq":
        ret = update_cq_action(args)
    elif args.action == "update-grafyaml":
        ret = update_grafyaml_action(args)
    exit(ret)


if __name__ == "__main__":
    main()
