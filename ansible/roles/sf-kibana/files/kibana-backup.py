#!/usr/bin/env python3

# Original source: https://github.com/selivan/kibana-backup-simple
# Small improvements are done in fork:
# https://github.com/danpawlik/kibana-backup-simple

# Kibana documentation:
# https://www.elastic.co/guide/en/kibana/current/saved-objects-api-export.html
# https://www.elastic.co/guide/en/kibana/current/saved-objects-api-import.html

import datetime
import json
import sys
import time
import argparse
import requests
import os
import yaml

# Error message from Kibana listing all possible saved objects types:
# \"type\" must be one of:
# [config, map, canvas-workpad, canvas-element, index-pattern,
#  visualization, search, dashboard, url]
saved_objects_types = ('config', 'map', 'canvas-workpad', 'canvas-element',
                       'index-pattern', 'visualization', 'search', 'dashboard',
                       'url')

to_remove_keys = ['updated_at', 'version', 'migrationVersion']


def get_arguments():
    args_parser = argparse.ArgumentParser(
        description='Backup and restore Kibana saved objects. '
        'Writes backup to stdout and reads from stdin.')
    args_parser.add_argument('action',
                             choices=['backup', 'restore', 'convert'])
    args_parser.add_argument('--kibana-url',
                             default='http://127.0.0.1:5601',
                             help='URL to access Kibana API')
    args_parser.add_argument('--space-id',
                             default='',
                             help='Kibana space id. If not set then the '
                             'default space is used.')
    args_parser.add_argument('--user', default='', help='Kibana user')
    args_parser.add_argument('--password', default='', help='Kibana password')
    args_parser.add_argument('--backup-dir',
                             help='Dir where backups will be stored')
    args_parser.add_argument('--file', help='File to restore or convert')
    args_parser.add_argument('--restore-file',
                             help='DEPRECATED: File to restore or convert')
    args_parser.add_argument('--resolve-conflicts',
                             default=True,
                             help='Resolve conflicts by removing index '
                             'id reference in backup file')
    args_parser.add_argument('--insecure',
                             action='store_true',
                             help='Use that option to ignore if SSL cert '
                             'has been verified by root CA')
    args_parser.add_argument('--extension',
                             default='ndjson',
                             help='Backup extension type')
    args_parser.add_argument('--tenant',
                             help='Specify tenant for getting data.'
                             'NOTE: if none is set, it will take Global')
    args_parser.add_argument('--all-tenants',
                             action='store_true',
                             help='Bakup all objects in all '
                             'tenants. Works only with backup.'
                             'NOTE: requires param: --elasticsearch-api-url')
    args_parser.add_argument('--elasticsearch-api-url',
                             default='https://localhost:9200',
                             help='Require to get all tenants available in '
                             'elasticsearch')
    return args_parser.parse_args()


def convert_to_yaml(text, remove_references):
    # reparse text
    text_lines = []
    try:
        for line in text:
            if isinstance(line, dict):
                text_lines.append(line)
            else:
                text_lines.append(json.loads(line))
    except Exception as e:
        print(e)

    if remove_references:
        text_lines = remove_reference(text_lines)
    return yaml.dump(text_lines)


def save_content_to_file(text, backup_file, extension, remove_references=True):
    if isinstance(text, dict):
        text = str(text)
    if extension in ['yaml', 'yml']:
        text = convert_to_yaml(text, remove_references)
    elif extension in ['json', 'ndjson'] and isinstance(text, list):
        text = " ".join(json.dumps(txt) + '\n' for txt in text)
    with open(backup_file, 'a') as f:
        f.write(text)


def parse_kibana_output(text):
    new_text = []
    try:
        text = [json.loads(text)]
    except json.decoder.JSONDecodeError:
        for text_obj in text.rsplit('\n'):
            n_text = json.loads(text_obj)
            new_text.append(n_text)
    return new_text if new_text else text


def check_if_empty(text):
    text = json.loads(text)
    if 'exportedCount' in text and text['exportedCount'] == 0:
        return True


def remove_obj_keys(ref):
    for k in to_remove_keys:
        ref.pop(k, None)
    return ref


def remove_reference(text):
    new_text = []
    new_references = []
    for text_obj in text:
        for ref in text_obj['references']:
            if (not ref.get('id').startswith('AX')
                    and len(ref.get('id')) != 20):
                new_references.append(remove_obj_keys(ref))
            text_obj['references'] = new_references
            new_text.append(text_obj)
    return new_text if new_text else text


def make_request(url, user, password, text, tenant, insecure=False,
                 retry=True):
    r = None
    headers = {'kbn-xsrf': 'reporting', 'osd-xsrf': 'true'}
    if tenant:
        headers['securitytenant'] = tenant

    try:
        r = requests.post(url,
                          auth=(user, password),
                          headers=headers,
                          files={'file': ('backup.ndjson', text)},
                          timeout=10,
                          verify=insecure)
    except requests.exceptions.ReadTimeout:
        if not retry:
            print("Importing failed. Retrying...")
            time.sleep(10)
            make_request(url, user, password, text, tenant, insecure)

    if r and "Please enter your credentials" in r.text:
        print("Please provide correct username and password")
        sys.exit(1)

    return r


def _get_file_content(backup_file):
    if (backup_file.endswith('yml') or backup_file.endswith('yaml')):
        with open(backup_file) as f:
            text = yaml.safe_load(f)
    else:
        with open(backup_file) as f:
            text = f.readlines()
    return text


def backup(kibana_url, space_id, user, password, backup_dir, insecure,
           tenant, extension='ndjson'):
    """Return string with newline-delimitered json containing
    Kibana saved objects"""
    saved_objects = {}
    if not backup_dir:
        backup_dir = os.path.dirname(os.path.realpath(__file__))

    # Set the same time for all backups if previous exists
    b_time = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M")

    if len(space_id):
        url = kibana_url + '/s/' + space_id + '/api/saved_objects/_export'
    else:
        url = kibana_url + '/api/saved_objects/_export'
    for obj_type in saved_objects_types:
        print("Working on %s" % obj_type)

        # osd-xsrf header is required by opensearch
        # https://opensearch.org/docs/latest/troubleshoot/index/
        headers = {'Content-Type': 'application/json',
                   'kbn-xsrf': 'reporting',
                   'osd-xsrf': 'true'}
        if tenant:
            headers['securitytenant'] = tenant

        r = requests.post(url,
                          auth=(user, password),
                          headers=headers,
                          data='{ "type": "' + obj_type +
                          '","excludeExportDetails": true}',
                          verify=insecure)

        if r.status_code == 400:
            # Print warning on missing object, but continue
            print("Can not backup object %s" % obj_type)
            continue
        else:
            r.raise_for_status()

        if not r.text:
            continue

        if tenant:
            backup_file = "%s/%s-%s.%s" % (backup_dir, obj_type, tenant,
                                           extension)
        else:
            backup_file = "%s/%s.%s" % (backup_dir, obj_type, extension)

        if os.path.exists(backup_file):
            backup_file = "%s-%s" % (backup_file, b_time)

        text = parse_kibana_output(r.text)
        saved_objects[obj_type] = text
        save_content_to_file(text, backup_file, extension)

    if tenant:
        backup_file = "%s/backup-%s.%s" % (backup_dir, tenant, extension)
    else:
        backup_file = "%s/backup.%s" % (backup_dir, extension)
    if os.path.exists(backup_file):
        backup_file = "%s-%s" % (backup_file, b_time)

    for kib_obj in saved_objects.values():
        save_content_to_file(kib_obj, backup_file, extension, False)


def restore(kibana_url, space_id, user, password, text, resolve_conflicts,
            insecure, tenant):
    """Restore given newline-delimitered json containing
    saved objects to Kibana"""

    if len(space_id):
        url = (kibana_url + '/s/' + space_id +
               '/api/saved_objects/_import?overwrite=true')
    else:
        url = kibana_url + '/api/saved_objects/_import?overwrite=true'

    if not isinstance(text, list):
        text = [text]

    for kib_obj in text:
        print("Working on %s" % kib_obj)

        if not isinstance(kib_obj, dict):
            # Ensure that the kib_obj is one-time converted json object
            kib_obj = json.dumps(json.loads(kib_obj))
        else:
            kib_obj = json.dumps(kib_obj)

        if check_if_empty(kib_obj):
            print("Spotted empty object. Continue...")
            continue

        r = make_request(url, user, password, kib_obj, tenant, insecure)

        if r.status_code == 401:
            print("Unauthorized. Please provide user and password")

        try:
            response_error = json.loads(r.text)
            if response_error.get('errors'):
                print("\n\nSome problem on restoring %s: %s\n\n" %
                      (kib_obj, response_error['errors']))
        except Exception as e:
            print("Kibana restore requests objects does not look correct:"
                  " %s" % e)

        if not r:
            print("Can not import %s into Kibana" % kib_obj)
            continue

        response_text = json.loads(r.text)
        if not response_text['success'] and resolve_conflicts:
            text = remove_reference(kib_obj)
            r = make_request(url, user, password, text, tenant, insecure)

        print(r.status_code, r.reason, '\n', r.text)
        r.raise_for_status()  # Raises stored HTTPError, if one occurred.


def convert(text, extension, convert_file):
    convert_file = "%s-converted.%s" % (convert_file, extension)
    save_content_to_file(text, convert_file, extension, False)


def get_all_tenants(elasticsearch_api_url, user, password, insecure):
    url = "%s/_opendistro/_security/api/tenants/" % elasticsearch_api_url
    r = requests.get(url, auth=(user, password), verify=insecure)
    if r.status_code != 200:
        r.raise_for_status()
        sys.exit(1)
    return list(json.loads(r.text))


if __name__ == '__main__':
    args = get_arguments()
    kibana_url = args.kibana_url

    if args.file and args.restore_file:
        print("Can not set both params: file and restore-file. Exit")
        sys.exit(1)

    if (not args.kibana_url.startswith('http')
            and not args.kibana_url.startswith('https')):
        kibana_url = "http://%s" % args.kibana_url

    if args.action == 'backup':
        if args.all_tenants and args.tenant:
            print("Can not use --all-tenants with --tenant option")
            sys.exit(1)

        if args.all_tenants:
            if not args.elasticsearch_api_url:
                print('Please provide --elasticsearch-api-url to list all'
                      ' tenants available in Elasticsearch.')
                sys.exit(1)
            all_tenants = get_all_tenants(args.elasticsearch_api_url,
                                          args.user, args.password,
                                          args.insecure)

            for tenant in all_tenants:
                backup(kibana_url, args.space_id, args.user, args.password,
                       args.backup_dir, args.insecure, tenant, args.extension)
        else:
            backup(kibana_url, args.space_id, args.user, args.password,
                   args.backup_dir, args.insecure, args.tenant, args.extension)

    elif args.action == 'restore':
        restore_file = args.file if args.file else args.restore_file
        if restore_file:
            text = _get_file_content(restore_file)
        else:
            text = ''.join(sys.stdin.readlines())

        restore(kibana_url, args.space_id, args.user, args.password, text,
                args.resolve_conflicts, args.insecure, args.tenant)

    elif args.action == 'convert':
        if args.file:
            text = _get_file_content(args.file)
        else:
            text = ''.join(sys.stdin.readlines())
        if not text:
            print("Can not continue. Did not provide --file param or stdin")
            sys.exit(1)

        convert(text, args.extension, args.file)
