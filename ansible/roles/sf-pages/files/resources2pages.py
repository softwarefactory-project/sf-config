#!/bin/env python

import os
import sys
import copy
import yaml
import requests

ZUUL_PAGES_FILE = "/var/lib/pagesuser/zuul_pages.yaml"
HTTPD_PAGES_FILE = "/var/lib/pagesuser/httpd_pages.conf"

ZUUL_PAGES_TMPL = {
    "name": None,
    "check": ["pages-render"],
    "gate": ["pages-render"],
    "post": ["pages-update"]}

HTTPD_PAGES_TMPL = """
<VirtualHost *:80>
    ServerName %(name)s
    ProxyPass / http://pages/html/pages/%(name)s/pages/
    ProxyPassReverse / http://pages/html/pages/%(name)s/pages/
</VirtualHost>
<VirtualHost *:443>
    ServerName %(name)s
    SSLEngine on
    SSLCertificateFile /etc/pki/tls/certs/%(fqdn)s.crt
    SSLCertificateChainFile /etc/pki/tls/certs/%(fqdn)s-chain.crt
    SSLCertificateKeyFile  /etc/pki/tls/private/%(fqdn)s.key
    ProxyPass / http://pages/html/pages/%(name)s/pages/
    ProxyPassReverse / http://pages/html/pages/%(name)s/pages/
</VirtualHost>
"""

if __name__ == "__main__":
    fqdn = sys.argv[1]
    resources = requests.get("http://managesf:20001/resources/").json()
    resources = resources['resources']
    zuul_pages_content = {"projects": []}
    httpd_pages_content = ""
    for repo in resources['repos']:
        if repo.endswith(".%s" % fqdn):
            print "Found pages repo %s" % repo
            zuul_page = copy.deepcopy(ZUUL_PAGES_TMPL)
            zuul_page['name'] = repo
            zuul_pages_content['projects'].append(zuul_page)
            httpd_vhost = copy.copy(HTTPD_PAGES_TMPL)
            httpd_vhost = httpd_vhost % {"fqdn": fqdn, "name": repo}
            httpd_pages_content += httpd_vhost
    yaml.safe_dump(zuul_pages_content,
                   file(ZUUL_PAGES_FILE, 'w'),
                   default_flow_style=False)
    file(HTTPD_PAGES_FILE, 'w').write(httpd_pages_content)
