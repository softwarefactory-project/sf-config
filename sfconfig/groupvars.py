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

import base64
import random
import os
import uuid

from sfconfig.utils import execute
from sfconfig.utils import yaml_dump
from sfconfig.utils import yaml_load


def encode_image(path):
    return base64.b64encode(open(path).read())


def get_sf_version():
    try:
        return open("/etc/sf-release").read().strip()
    except IOError:
        return "master"


def get_previous_version():
    try:
        return open("/var/lib/software-factory/.version").read().strip()
    except IOError:
        return "2.5.0"


def get_default(d, key, default):
    val = d.get(key, default)
    if not val:
        val = default
    return val


def generate(arch, sfmain, args):
    """ This function 'glue' all roles and convert sfconfig.yaml """
    secrets = yaml_load("%s/secrets.yaml" % args.lib)

    # Cleanup obsolete secrets
    for unused in ("mumble_ice_secret", ):
        if unused in secrets:
            del secrets[unused]

    # Generate all variable when the value is CHANGE_ME
    defaults = {}
    for role in arch["roles"]:
        role_vars = yaml_load("%s/ansible/roles/sf-%s/defaults/main.yml" % (
                              args.share, role))
        defaults.update(role_vars)
        for key, value in role_vars.items():
            if str(value).strip().replace('"', '') == 'CHANGE_ME':
                if key not in secrets:
                    secrets[key] = str(uuid.uuid4())

    # Generate dynamic role variable in the glue dictionary
    glue = {'mysql_databases': {},
            'sf_tasks_dir': "%s/ansible/tasks" % args.share,
            'sf_templates_dir': "%s/templates" % args.share,
            'sf_playbooks_dir': "%s" % args.ansible_root,
            'jobs_zmq_publishers': [],
            'loguser_authorized_keys': [],
            'pagesuser_authorized_keys': [],
            'logservers': []}

    def get_hostname(role):
        if len(arch["roles"][role]) != 1:
            raise RuntimeError("Role %s is defined on multi-host" % role)
        return arch["roles"][role][0]["hostname"]

    def get_or_generate_ssh_key(name):
        priv = "%s/ssh_keys/%s" % (args.lib, name)
        pub = "%s/ssh_keys/%s.pub" % (args.lib, name)

        if not os.path.isfile(priv):
            execute(["ssh-keygen", "-t", "rsa", "-N", "", "-f", priv, "-q"])
        glue[name] = open(priv).read()
        glue["%s_pub" % name] = open(pub).read()

    def get_or_generate_cauth_keys():
        priv_file = "%s/certs/cauth_privkey.pem" % args.lib
        pub_file = "%s/certs/cauth_pubkey.pem" % args.lib
        if not os.path.isfile(priv_file):
            execute(["openssl", "genrsa", "-out", priv_file, "1024"])
        if not os.path.isfile(pub_file):
            execute(["openssl", "rsa", "-in", priv_file, "-out", pub_file,
                     "-pubout"])
        glue["cauth_privkey"] = open(priv_file).read()
        glue["cauth_pubkey"] = open(pub_file).read()

    def get_or_generate_localCA():
        ca_file = "%s/certs/localCA.pem" % args.lib
        ca_key_file = "%s/certs/localCAkey.pem" % args.lib
        ca_srl_file = "%s/certs/localCA.srl" % args.lib
        gateway_cnf = "%s/certs/gateway.cnf" % args.lib
        gateway_key = "%s/certs/gateway.key" % args.lib
        gateway_req = "%s/certs/gateway.req" % args.lib
        gateway_crt = "%s/certs/gateway.crt" % args.lib
        gateway_pem = "%s/certs/gateway.pem" % args.lib

        def xunlink(filename):
            if os.path.isfile(filename):
                os.unlink(filename)

        # First manage CA
        if not os.path.isfile(ca_file):
            # When CA doesn't exists, remove all certificates
            for fn in [gateway_cnf, gateway_req, gateway_crt]:
                xunlink(fn)
            # Generate a random OU subject to be able to trust multiple sf CA
            ou = ''.join(random.choice('0123456789abcdef') for n in range(6))
            execute(["openssl", "req", "-nodes", "-days", "3650", "-new",
                     "-x509", "-subj", "/C=FR/O=SoftwareFactory/OU=%s" % ou,
                     "-keyout", ca_key_file, "-out", ca_file])

        if not os.path.isfile(ca_srl_file):
            open(ca_srl_file, "w").write("00\n")

        if os.path.isfile(gateway_cnf) and \
                open(gateway_cnf).read().find("DNS.1 = %s\n" %
                                              sfmain["fqdn"]) == -1:
            # if FQDN changed, remove all certificates
            for fn in [gateway_cnf, gateway_req, gateway_crt]:
                xunlink(fn)

        # Then manage certificate request
        if not os.path.isfile(gateway_cnf):
            open(gateway_cnf, "w").write("""[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name

[ req_distinguished_name ]
commonName_default = %s

[ v3_req ]
subjectAltName=@alt_names

[alt_names]
DNS.1 = %s
""" % (sfmain["fqdn"], sfmain["fqdn"]))

        if not os.path.isfile(gateway_key):
            if os.path.isfile(gateway_req):
                xunlink(gateway_req)
            execute(["openssl", "genrsa", "-out", gateway_key, "2048"])

        if not os.path.isfile(gateway_req):
            if os.path.isfile(gateway_crt):
                xunlink(gateway_crt)
            execute(["openssl", "req", "-new", "-subj",
                     "/C=FR/O=SoftwareFactory/CN=%s" % sfmain["fqdn"],
                     "-extensions", "v3_req", "-config", gateway_cnf,
                     "-key", gateway_key, "-out", gateway_req])

        if not os.path.isfile(gateway_crt):
            if os.path.isfile(gateway_pem):
                xunlink(gateway_pem)
            execute(["openssl", "x509", "-req", "-days", "3650", "-sha256",
                     "-extensions", "v3_req", "-extfile", gateway_cnf,
                     "-CA", ca_file, "-CAkey", ca_key_file,
                     "-CAserial", ca_srl_file,
                     "-in", gateway_req, "-out", gateway_crt])

        if not os.path.isfile(gateway_pem):
            open(gateway_pem, "w").write("%s\n%s\n" % (
                open(gateway_key).read(), open(gateway_crt).read()))

        glue["localCA_pem"] = open(ca_file).read()
        glue["gateway_crt"] = open(gateway_crt).read()
        glue["gateway_key"] = open(gateway_key).read()
        glue["gateway_chain"] = glue["gateway_crt"]

    glue["gateway_url"] = "https://%s" % sfmain["fqdn"]
    glue["sf_version"] = get_sf_version()
    glue["sf_previous_version"] = get_previous_version()

    if sfmain["debug"]:
        for service in ("managesf", "zuul", "nodepool"):
            glue["%s_loglevel" % service] = "DEBUG"
            glue["%s_root_loglevel" % service] = "INFO"

    if "cauth" in arch["roles"]:
        get_or_generate_cauth_keys()
        glue["cauth_host"] = get_hostname("cauth")

    if "gateway" in arch["roles"]:
        get_or_generate_localCA()
        glue["gateway_host"] = get_hostname("gateway")
        glue["gateway_topmenu_logo_data"] = encode_image(
            "/etc/software-factory/logo-topmenu.png")
        glue["gateway_favicon_data"] = encode_image(
            "/etc/software-factory/logo-favicon.ico")
        glue["gateway_splash_image_data"] = encode_image(
            "/etc/software-factory/logo-splash.png")

    if "install-server" in arch["roles"]:
        get_or_generate_ssh_key("service_rsa")
        glue["install_server_host"] = get_hostname("install-server")

    if "mysql" in arch["roles"]:
        glue["mysql_host"] = get_hostname("mysql")

    if "zookeeper" in arch["roles"]:
        glue["zookeeper_host"] = get_hostname("zookeeper")

    if "cauth" in arch["roles"]:
        glue["cauth_mysql_host"] = get_hostname("mysql")
        glue["mysql_databases"]["cauth"] = {
            'hosts': ['localhost', get_hostname("cauth")],
            'user': 'cauth',
            'password': secrets['cauth_mysql_password'],
        }

    if "managesf" in arch["roles"]:
        glue["managesf_host"] = get_hostname("managesf")
        glue["managesf_internal_url"] = "http://%s:%s" % (
            get_hostname("managesf"), defaults["managesf_port"])
        glue["managesf_mysql_host"] = get_hostname("mysql")
        glue["mysql_databases"]["managesf"] = {
            'hosts': ['localhost', get_hostname("managesf")],
            'user': 'managesf',
            'password': secrets['managesf_mysql_password'],
        }

    if "gerrit" in arch["roles"]:
        glue["gerrit_host"] = get_hostname("gerrit")
        glue["gerrit_pub_url"] = "%s/r/" % glue["gateway_url"]
        glue["gerrit_internal_url"] = "http://%s:%s/r/" % (
            get_hostname("gerrit"), defaults["gerrit_port"])
        glue["gerrit_email"] = "gerrit@%s" % sfmain["fqdn"]
        glue["gerrit_mysql_host"] = glue["mysql_host"]
        glue["mysql_databases"]["gerrit"] = {
            'hosts': list(set(('localhost',
                               get_hostname("gerrit"),
                               get_hostname("managesf")))),
            'user': 'gerrit',
            'password': secrets['gerrit_mysql_password'],
        }
        get_or_generate_ssh_key("gerrit_service_rsa")
        get_or_generate_ssh_key("gerrit_admin_rsa")
        if sfmain["network"]["disable_external_resources"]:
            glue["gerrit_replication"] = False

    if "jenkins" in arch["roles"]:
        glue["jenkins_host"] = get_hostname("jenkins")
        glue["jenkins_internal_url"] = "http://%s:%s/jenkins/" % (
            get_hostname("jenkins"), defaults["jenkins_http_port"])
        glue["jenkins_api_url"] = "http://%s:%s/jenkins/" % (
            get_hostname("jenkins"), defaults["jenkins_api_port"])
        glue["jenkins_pub_url"] = "%s/jenkins/" % glue["gateway_url"]
        get_or_generate_ssh_key("jenkins_rsa")
        glue["jobs_zmq_publishers"].append(
            "tcp://%s:8889" % glue["jenkins_host"])

    if "zuul" in arch["roles"]:
        if ("nodepool" not in arch["roles"] or
            len(sfmain["nodepool"].get("providers", [])) == 0 or (
                len(sfmain["nodepool"]["providers"]) == 1 and
                not sfmain["nodepool"]["providers"][0]["auth_url"])):
            glue["zuul_offline_node_when_complete"] = False
        get_or_generate_ssh_key("jenkins_rsa")
        glue["zuul_pub_url"] = "%s/zuul/" % glue["gateway_url"]
        glue["zuul_internal_url"] = "http://%s:%s/" % (
            get_hostname("zuul-server"), defaults["zuul_port"])
        glue["zuul_mysql_host"] = glue["mysql_host"]
        glue["mysql_databases"]["zuul"] = {
            'hosts': ["localhost", get_hostname("zuul-server")],
            'user': 'zuul',
            'password': secrets['zuul_mysql_password'],
        }

    if "zuul-server" in arch["roles"]:
        glue["zuul_server_host"] = get_hostname("zuul-server")

    if "zuul-launcher" in arch["roles"]:
        glue["zuul_launcher_host"] = get_hostname("zuul-launcher")
        glue["jobs_zmq_publishers"].append(
            "tcp://%s:8888" % glue["zuul_launcher_host"])
        glue["loguser_authorized_keys"].append(glue["jenkins_rsa_pub"])
        glue["zuul_static_nodes"] = sfmain.get(
            'zuul', {}).get('static_nodes', [])

    if "nodepool" in arch["roles"]:
        glue["nodepool_providers"] = sfmain["nodepool"].get("providers", [])
        glue["nodepool_mysql_host"] = glue["mysql_host"]
        glue["mysql_databases"]["nodepool"] = {
            'hosts': ["localhost", get_hostname("nodepool-launcher")],
            'user': 'nodepool',
            'password': secrets['nodepool_mysql_password'],
        }
        if sfmain["network"]["disable_external_resources"]:
            glue["nodepool_disable_providers"] = True

    if "nodepool-launcher" in arch["roles"]:
        glue["nodepool_launcher_host"] = get_hostname("nodepool-launcher")

    if "nodepool-builder" in arch["roles"]:
        glue["nodepool_builder_host"] = get_hostname("nodepool-builder")

    if "zuul" in arch["roles"] or "zuul3" in arch["roles"]:
        get_or_generate_ssh_key("zuul_rsa")

# ZuulV3 and NodepoolV3
    if "zuul3" in arch["roles"]:
        glue["zuul3_pub_url"] = "%s/zuul3/" % glue["gateway_url"]
        glue["zuul3_internal_url"] = "http://%s:%s/" % (
            get_hostname("zuul3-scheduler"), defaults["zuul3_port"])
        glue["zuul3_mysql_host"] = glue["mysql_host"]
        glue["mysql_databases"][defaults["zuul3_mysql_db"]] = {
            'hosts': ["localhost", get_hostname("zuul3-scheduler")],
            'user': defaults["zuul3_mysql_user"],
            'password': secrets["zuul3_mysql_password"],
        }
        glue["loguser_authorized_keys"].append(glue["zuul_rsa_pub"])

    if "zuul3-scheduler" in arch["roles"]:
        glue["zuul3_scheduler_host"] = get_hostname("zuul3-scheduler")

    if "zuul3-executor" in arch["roles"]:
        glue["zuul3_executor_host"] = get_hostname("zuul3-executor")

    if "zuul3-web" in arch["roles"]:
        glue["zuul3_web_host"] = get_hostname("zuul3-web")

    if "nodepool3" in arch["roles"]:
        glue["nodepool3_providers"] = sfmain.get("nodepool3", {}).get(
            "providers", [])
        get_or_generate_ssh_key("nodepool_rsa")

    if "logserver" in arch["roles"]:
        glue["logserver_host"] = get_hostname("logserver")
        glue["logservers"].append({
            "name": "sflogs",
            "host": glue["logserver_host"],
            "user": "loguser",
            "path": "/var/www/logs",
        })

    if "elasticsearch" in arch["roles"]:
        glue["elasticsearch_host"] = get_hostname("elasticsearch")

    if "pages" in arch["roles"]:
        glue["pages_host"] = get_hostname("pages")
        glue["pages"] = {
            "name": "pages",
            "host": glue["pages_host"],
            "user": "pagesuser",
            "path": "/var/www/html/pages",
        }
        glue["pagesuser_authorized_keys"].append(glue["jenkins_rsa_pub"])

    if "firehose" in arch["roles"]:
        glue["firehose_host"] = get_hostname("firehose")

    if "grafana" in arch["roles"]:
        glue["grafana_host"] = get_hostname("grafana")
        glue["grafana_internal_url"] = "http://%s:%s" % (
            get_hostname("grafana"), defaults["grafana_http_port"])
        glue["grafana_mysql_host"] = get_hostname("mysql")
        glue["mysql_databases"]["grafana"] = {
            'hosts': ['localhost', get_hostname("grafana")],
            'user': 'grafana',
            'password': secrets['grafana_mysql_password'],
        }

    if "influxdb" in arch["roles"]:
        glue["influxdb_host"] = get_hostname("influxdb")

    if "lodgeit" in arch["roles"]:
        glue["lodgeit_mysql_host"] = get_hostname("mysql")
        glue["mysql_databases"]["lodgeit"] = {
            'hosts': ['localhost', get_hostname("lodgeit")],
            'user': 'lodgeit',
            'password': secrets['lodgeit_mysql_password'],
        }

    if "etherpad" in arch["roles"]:
        glue["etherpad_mysql_host"] = get_hostname("mysql")
        glue["mysql_databases"]["etherpad"] = {
            'hosts': ['localhost', get_hostname("etherpad")],
            'user': 'etherpad',
            'password': secrets['etherpad_mysql_password'],
        }

    if "storyboard" in arch["roles"]:
        glue["storyboard_mysql_host"] = glue["mysql_host"]
        glue["storyboard_host"] = get_hostname("storyboard")
        glue["storyboard_internal_url"] = "http://%s:%s/v1/" % (
            glue["storyboard_host"], defaults["storyboard_http_port"])
        glue["mysql_databases"]["storyboard"] = {
            'hosts': ["localhost", get_hostname("storyboard")],
            'user': 'storyboard',
            'password': secrets["storyboard_mysql_password"],
        }

    if "murmur" in arch["roles"]:
        if sfmain["mumble"].get("password"):
            glue["murmur_password"] = sfmain["mumble"].get("password")

    if "koji_host" in sfmain["network"] and sfmain["network"]["koji_host"]:
        glue["koji_host"] = sfmain["network"]["koji_host"]

    # Extra zuul settings
    zuul_config = sfmain.get("zuul", {})
    for logserver in zuul_config.get("external_logserver", []):
        server = {
            "name": logserver["name"],
            "host": logserver.get("host", logserver["name"]),
            "user": logserver.get("user", "zuul"),
            "path": logserver["path"],
        }
        glue["logservers"].append(server)
    glue["zuul_log_url"] = get_default(
        zuul_config,
        "log_url",
        "%s/logs/{build.parameters[LOG_PATH]}" % glue["gateway_url"])
    glue["zuul_default_log_site"] = get_default(
        zuul_config, "default_log_site", "sflogs")
    glue["zuul_extra_gerrits"] = zuul_config.get("gerrit_connections", [])

    # Zuul known hosts
    glue["zuul_ssh_known_hosts"] = []
    if "gerrit" in arch["roles"]:
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": "[%s]:29418" % glue["gerrit_host"],
                "host": glue["gerrit_host"],
                "port": "29418",
            }
        )
    for logserver in zuul_config.get("external_logserver", []):
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": logserver.get("hostname", logserver["name"]),
                "host": logserver.get("hostname", logserver["name"]),
                "port": "22",
            }
        )
    for extra_gerrit in glue.get("zuul_extra_gerrits", []):
        if extra_gerrit.get("port", 29418) == 22:
            host_packed = extra_gerrit["hostname"]
        else:
            host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                       extra_gerrit.get("port", 29418))
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": host_packed,
                "host": extra_gerrit["hostname"],
                "port": extra_gerrit.get("port", 29418)
            }
        )

    for static_node in glue.get("zuul_static_nodes", []):
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": static_node.get("hostname"),
                "host": static_node.get("hostname"),
                "port": 22
            }
        )

    if "logserver" in arch["roles"] and \
       glue["logserver_host"] != glue["install_server_host"]:
        glue["zuul_ssh_known_hosts"].append(
            {
                "host_packed": glue["logserver_host"],
                "host": glue["logserver_host"],
                "port": 22
            }
        )

    if "elasticsearch" in sfmain:
        if 'heap_size' in sfmain['elasticsearch']:
            glue['elasticsearch_heap_size'] = sfmain[
                'elasticsearch']['heap_size']
        if 'replicas' in sfmain['elasticsearch']:
            glue['elasticsearch_replicas'] = sfmain[
                'elasticsearch']['replicas']

    if "logstash" in sfmain:
        if 'retention_days' in sfmain['logstash']:
            glue['logstash_retention_days'] = \
                sfmain['logstash']['retention_days']

    # Extra zuul3 settings
    zuul3_config = sfmain.get("zuul3", {})
    glue["zuul3_extra_gerrits"] = zuul3_config.get("gerrit_connections", [])
    glue["zuul3_success_log_url"] = get_default(
        zuul3_config, "success_log_url",
        "%s/logs/{build.uuid}/" % glue["gateway_url"]
    )
    glue["zuul3_failure_log_url"] = get_default(
        zuul3_config, "failure_log_url",
        "%s/logs/{build.uuid}/" % glue["gateway_url"]
    )
    glue["zuul3_ssh_known_hosts"] = []
    glue["zuul3_github_connections"] = []
    if "gerrit" in arch["roles"]:
        glue["zuul3_ssh_known_hosts"].append(
            {
                "host_packed": "[%s]:29418" % glue["gerrit_host"],
                "host": glue["gerrit_host"],
                "port": "29418",
            }
        )
    for extra_gerrit in glue.get("zuul3_extra_gerrits", []):
        if extra_gerrit.get("port", 29418) == 22:
            host_packed = extra_gerrit["hostname"]
        else:
            host_packed = "[%s]:%s" % (extra_gerrit["hostname"],
                                       extra_gerrit.get("port", 29418))
        glue["zuul3_ssh_known_hosts"].append(
            {
                "host_packed": host_packed,
                "host": extra_gerrit["hostname"],
                "port": extra_gerrit.get("port", 29418)
            }
        )
    if "logserver" in arch["roles"]:
        glue["zuul3_ssh_known_hosts"].append(
            {
                "host_packed": glue["logserver_host"],
                "host": glue["logserver_host"],
                "port": 22
            }
        )
    for github_connection in zuul3_config.get("github_connections", []):
        if github_connection.get("port", 22) == 22:
            host_packed = github_connection.get("hostname", "github.com")
        else:
            host_packed = "[%s]:%s" % (github_connection["hostname"],
                                       github_connection["port"])
        glue["zuul3_ssh_known_hosts"].append(
            {
                "host_packed": host_packed,
                "host": github_connection.get("hostname", "github.com"),
                "port": github_connection.get("port", 22)
            }
        )
        glue["zuul3_github_connections"].append(github_connection)

    # Save secrets to new secrets file
    yaml_dump(secrets, open("%s/secrets.yaml" % args.lib, "w"))
    glue.update(secrets)
    return glue
