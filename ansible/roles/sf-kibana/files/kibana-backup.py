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
    return args_parser.parse_args()


def convert_to_yaml(text, remove_references):
    if remove_references:
        text = remove_reference(text)
    return yaml.dump(json.loads(text))


def save_content_to_file(text, backup_file, extension, remove_references=True):
    if extension in ['yaml', 'yml']:
        text = convert_to_yaml(text, remove_references)
    with open(backup_file, 'a') as f:
        f.write(text)


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
    try:
        text = json.loads(text)
        for ref in text['references']:
            if not ref.get('id').startswith('AX') and len(ref.get('id')) != 20:
                new_references.append(remove_obj_keys(ref))
        text['references'] = new_references
    except json.decoder.JSONDecodeError:
        raise ("Can not remove reference! Bad malformed ndjson file")
        sys.exit(1)

    return json.dumps(new_text) if new_text else json.dumps(text)


def make_request(url, user, password, text, insecure=False, retry=True):
    r = None
    try:
        r = requests.post(url,
                          auth=(user, password),
                          headers={'kbn-xsrf': 'reporting'},
                          files={'file': ('backup.ndjson', text)},
                          timeout=10,
                          verify=insecure)
    except requests.exceptions.ReadTimeout:
        if not retry:
            print("Importing failed. Retrying...")
            time.sleep(10)
            make_request(url, user, password, text, insecure)

    if r and "Please enter your credentials" in r.text:
        print("Please provide correct username and password")
        sys.exit(1)

    return r


def _get_file_content(backup_file, extension=None):
    if (args.file.endswith('yml') or args.file.endswith('yaml')):
        extension = 'yaml'
        with open(args.file) as f:
            text = yaml.safe_load(f)
    else:
        with open(args.file) as f:
            text = f.readlines()
        extension = 'json'
    return text, extension


def backup(kibana_url,
           space_id,
           user,
           password,
           backup_dir,
           insecure,
           extension='ndjson'):
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
        r = requests.post(url,
                          auth=(user, password),
                          headers={
                              'Content-Type': 'application/json',
                              'kbn-xsrf': 'reporting'
                          },
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

        backup_file = "%s/%s.%s" % (backup_dir, obj_type, extension)
        if os.path.exists(backup_file):
            backup_file = "%s-%s" % (backup_file, b_time)

        saved_objects[obj_type] = r.text
        save_content_to_file(r.text, backup_file, extension)

    backup_file = "%s/backup.ndjson" % backup_dir
    if os.path.exists(backup_file):
        backup_file = "%s-%s" % (backup_file, b_time)
    with open(backup_file, 'a') as f:
        f.write('\n'.join(saved_objects.values()))


def restore(kibana_url, space_id, user, password, text, resolve_conflicts,
            insecure, extension):
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

        r = make_request(url, user, password, kib_obj, insecure)

        if r.status_code == 401:
            print("Unauthorized. Please provide user and password")

        try:
            response_error = json.loads(r.text)
            if response_error['errors']:
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
            r = make_request(url, user, password, text, insecure)

        print(r.status_code, r.reason, '\n', r.text)
        r.raise_for_status()  # Raises stored HTTPError, if one occurred.


def convert(text, extension, convert_file):
    convert_file = "%s-converted.%s" % (convert_file, extension)
    for kib_obj in text:
        save_content_to_file(kib_obj, convert_file, extension, False)


if __name__ == '__main__':
    args = get_arguments()
    kibana_url = args.kibana_url
    if (not args.kibana_url.startswith('http')
            and not args.kibana_url.startswith('https')):
        kibana_url = "http://%s" % args.kibana_url

    if args.action == 'backup':
        backup(kibana_url, args.space_id, args.user, args.password,
               args.backup_dir, args.insecure, args.extension)

    elif args.action == 'restore':
        if args.file:
            text, extension = _get_file_content(args.file, args.extension)
        else:
            text = ''.join(sys.stdin.readlines())

        restore(kibana_url, args.space_id, args.user, args.password, text,
                args.resolve_conflicts, args.insecure, extension)
    elif args.action == 'convert':
        if args.file:
            text, extension = _get_file_content(args.file, args.extension)
        else:
            text = ''.join(sys.stdin.readlines())

        convert(text, args.extension, args.file)
