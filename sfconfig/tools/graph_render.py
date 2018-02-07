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


def get_rows(datafile):
    rows = {}
    if os.path.isfile(datafile):
        rows = sfconfig.utils.yaml_load(datafile)
    return rows


def main():
    args = usage()
    data = {
        "tenants": get_tenants(args.zuul_url) if not args.check else [
            {"name": "test", "pipelines": ["check", "gate"]}],
        "providers": get_providers(args.config_dir) if not args.check else [
            {"name": "localhost", "driver": "oci"},
            {"name": "rdo", "driver": "openstack"}],
    }
    for template in glob.glob("%s/metrics/*.j2" % args.config_dir):
        name = os.path.basename(template).replace(".j2", "")
        datafile = os.path.basename(template).replace(".yaml.j2", "_data.yaml")
        datafile = os.path.join("%s/metrics/%s" % (args.config_dir, datafile))
        rows = get_rows(datafile)
        data.update(rows)
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
