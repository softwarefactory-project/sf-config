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
import glob

import sfconfig.utils


def usage():
    p = argparse.ArgumentParser(
        description="Generate dynamic grafyaml dashboard")
    p.add_argument("--zuul-url")
    p.add_argument("--config-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if not args.check and not args.zuul_url:
        print("usage: --zuul-url is needed")
        exit(1)
    return args


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


def get_extra_data(datafile):
    extra_data = {}
    if os.path.isfile(datafile):
        extra_data = sfconfig.utils.yaml_load(datafile)
    return extra_data


def create_continuous_queries(continuous_queries):
    secret_file = '/var/lib/software-factory/bootstrap-data/secrets.yaml'
    user = 'influxdb_admin_password'
    secret = sfconfig.utils.get_secret(user, secret_file)
    for query in continuous_queries:
        command = 'CREATE CONTINUOUS QUERY "qc_%s" ' % query['dest']
        command += 'ON "telegraf" '
        if query['resample_time']:
            command += 'RESAMPLE FOR %s ' % query['resample_time']
        command += 'BEGIN SELECT %s("value") as value ' % query['function']
        command += 'INTO "%s" ' % query['dest']
        command += 'FROM %s ' % query['measurement']
        command += 'GROUP BY time(%s) ' % query['time']
        if query['resample_fill']:
            command += 'fill(%s) ' % query['resample_fill']
        command += 'END'
        influx_cmd = [
            'influx', '-ssl', '-unsafeSsl', '-username', 'admin', '-password',
            '%s' % secret, '-database', 'telegraf', '-execute', '%s' % command]
        sfconfig.utils.execute(influx_cmd)


def main():
    args = usage()
    config_dir = args.config_dir
    for template in glob.glob("%s/metrics/*.j2" % config_dir):
        data = {
            "tenants": get_tenants(args.zuul_url) if not args.check else [
                {"name": "test", "pipelines": ["check", "gate"]}],
            "providers": get_providers(config_dir) if not args.check else [
                {"name": "localhost", "driver": "oci"},
                {"name": "rdo", "driver": "openstack"}],
        }
        name = os.path.basename(template).replace(".j2", "")
        if not args.check:
            datafile = os.path.basename(template).replace(".yaml.j2", "_data")
            datafile = os.path.join("%s/metrics/%s" % (config_dir, datafile))
            extra_data = get_extra_data(datafile)
            data.update(extra_data)

        if 'continuous_queries' in data and not args.check:
            create_continuous_queries(data['continuous_queries'])

        if name == "_nodepool-provider.yaml":
            for provider in data["providers"]:
                name = "%s-%s.yaml" % (name.replace(".yaml", ""),
                                       provider["name"])
                sfconfig.utils.render_template(
                    os.path.join(args.output_dir, name),
                    template, provider)
        else:
            sfconfig.utils.render_template(
                os.path.join(args.output_dir, name),
                template, data)


if __name__ == "__main__":
    main()
